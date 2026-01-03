import re

from rest_framework import serializers
from django.contrib.auth.models import User

from accounts.models import Profile, OrganizationMember, Organization
from accounts.messages import get_response_messages

MESSAGES = get_response_messages()


def split_name(full_name):
    name_parts = full_name.split()

    first_name = name_parts[0]

    last_name = ' '.join(name_parts[1:])

    return first_name, last_name

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(required=False)
    full_name = serializers.CharField(required=True)
    invitation_token = serializers.CharField(required=False)

    def validate_password(self, password):
        password_len = len(password)

        if password_len < 8:
            raise serializers.ValidationError(
                'Password length is too small. Must be at least 8 characters.'
            )
        elif password_len > 40:
            raise serializers.ValidationError(
                'Password length is too long. Must be less than 40 characters.'
            )

        if not re.search(r'[a-z]', password):
            raise serializers.ValidationError(
                'Password must contain at least one lowercase letter.'
            )
        if not re.search(r'[A-Z]', password):
            raise serializers.ValidationError(
                'Password must contain at least one uppercase letter.'
            )
        if not re.search(r'[0-9]', password):
            raise serializers.ValidationError('Password must contain at least one digit.')
        if not re.search(r'[!@#$%^&*]', password):
            raise serializers.ValidationError(
                'Password must contain at least one special character (!, @, #, $, %, ^, &, *)'
            )
        return password

    class Meta:
        model = User
        fields = '__all__'

    def create(self, validated_data):
        first_name, last_name = split_name(validated_data['full_name'])
        user = User(
            email=validated_data['email'].lower(),
            username=validated_data['email'].lower(),
            first_name=first_name,
            last_name=last_name,
            is_active=False,
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = '__all__'


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)

    def validate(self, data):
        email = data.get('email', '')
        password = data.get('password', '')

        if email == '':
            raise serializers.ValidationError({'error': MESSAGES.get('require.email')})
        elif password == '':
            raise serializers.ValidationError({'error': MESSAGES.get('require.password')})

        return data


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate(self, data):
        email = data.get('email', '')
        if email == '':
            raise serializers.ValidationError({'error': MESSAGES.get('require.email')})
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError('The new password and confirm password do not match.')
        return data

    def save(self, user):
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class ProfileSecurityBodySerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()



class OrganizationMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationMember
        fields = '__all__'


class AddMembersSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, allow_blank=False)
    role = serializers.ChoiceField(
        choices=[OrganizationMember.ADMIN, OrganizationMember.USER, OrganizationMember.OWNER],
        allow_blank=False,
        required=True,
        error_messages={'invalid_choice': 'Invalid role. Please select either admin or user.'},
    )


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class RoleUpdateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = OrganizationMember
        fields = ['id', 'role']
