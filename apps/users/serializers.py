from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from .models import User, UserProfile


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'password_confirm', 'first_name', 'last_name', 'role']
        extra_kwargs = {
            'role': {'required': False},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        # Only allow student/educator roles on self-registration
        if attrs.get('role') == User.Role.ADMIN:
            raise serializers.ValidationError({'role': 'Cannot self-register as admin.'})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        #UserProfile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs['email'], password=attrs['password'])
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        if not user.is_active:
            raise serializers.ValidationError('This account has been deactivated.')
        attrs['user'] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'total_quizzes_taken', 'total_questions_answered',
            'total_correct_answers', 'total_points', 'streak_days',
            'last_activity_date', 'accuracy_percentage',
            'preferred_difficulty', 'preferred_topics',
        ]
        read_only_fields = [
            'total_quizzes_taken', 'total_questions_answered',
            'total_correct_answers', 'total_points', 'streak_days',
            'last_activity_date', 'accuracy_percentage',
        ]


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'full_name',
            'role', 'bio', 'avatar_url', 'email_verified', 'date_joined',
            'last_login', 'profile',
        ]
        read_only_fields = ['id', 'email', 'email_verified', 'date_joined', 'last_login', 'role']


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'bio', 'avatar_url']


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': 'Incorrect password.'})
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'New passwords do not match.'})
        return attrs


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['preferred_difficulty', 'preferred_topics']


class AdminUserSerializer(serializers.ModelSerializer):
    """Full user info for admins."""
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = '__all__'
        read_only_fields = ['id', 'date_joined', 'last_login']
