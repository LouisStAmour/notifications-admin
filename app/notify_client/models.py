from itertools import chain

from flask import request, session
from flask_login import AnonymousUserMixin, UserMixin

roles = {
    'send_messages': ['send_texts', 'send_emails', 'send_letters'],
    'manage_templates': ['manage_templates'],
    'manage_service': ['manage_users', 'manage_settings'],
    'manage_api_keys': ['manage_api_keys']
}

# same dict as above, but flipped round (and with view_activity)
roles_by_permission = {
    'send_texts': 'send_messages',
    'send_emails': 'send_messages',
    'send_letters': 'send_messages',

    'manage_users': 'manage_service',
    'manage_settings': 'manage_service',

    'manage_templates': 'manage_templates',

    'manage_api_keys': 'manage_api_keys',
    'view_activity': 'view_activity',
}

all_permissions = set(roles_by_permission.values())


def _get_service_id_from_view_args():
    return request.view_args.get('service_id', None)


def translate_permissions_from_db_to_admin_roles(permissions):
    """
    Given a list of database permissions, return a set of roles

    look them up in roles_by_permission, falling back to just passing through from the api if they aren't in the dict
    """
    return {roles_by_permission.get(permission, permission) for permission in permissions}


def translate_permissions_from_admin_roles_to_db(permissions):
    """
    Given a list of admin roles (ie: checkboxes on a permissions edit page for example), return a set of db permissions

    Looks them up in the roles dict, falling back to just passing through if they're not recognised.
    """
    return set(chain.from_iterable(roles.get(permission, [permission]) for permission in permissions))


class User(UserMixin):
    def __init__(self, fields, max_failed_login_count=3):
        self._id = fields.get('id')
        self._name = fields.get('name')
        self._email_address = fields.get('email_address')
        self._mobile_number = fields.get('mobile_number')
        self._password_changed_at = fields.get('password_changed_at')
        self._set_permissions(fields.get('permissions', {}))
        self._auth_type = fields.get('auth_type')
        self._failed_login_count = fields.get('failed_login_count')
        self._state = fields.get('state')
        self.max_failed_login_count = max_failed_login_count
        self.platform_admin = fields.get('platform_admin')
        self.current_session_id = fields.get('current_session_id')
        self._organisations = fields.get('organisations', [])

    def _set_permissions(self, permissions_by_service):
        """
        Permissions is a dict {'service_id': ['permission a', 'permission b', 'permission c']}

        The api currently returns some granular permissions that we don't set or use separately (but may want
        to in the future):
        * send_texts, send_letters and send_emails become send_messages
        * manage_user and manage_settings become
        users either have all three permissions for a service or none of them, they're not helpful to distinguish
        between on the front end. So lets collapse them into "send_messages" and "manage_service". If we want to split
        them out later, we'll need to rework this function.
        """

        self._permissions = {
            service: translate_permissions_from_db_to_admin_roles(permissions)
            for service, permissions
            in permissions_by_service.items()
        }

    def get_id(self):
        return self.id

    def logged_in_elsewhere(self):
        # if the current user (ie: db object) has no session, they've never logged in before
        return self.current_session_id is not None and session.get('current_session_id') != self.current_session_id

    @property
    def is_active(self):
        return self.state == 'active'

    @property
    def is_authenticated(self):
        return (
            not self.logged_in_elsewhere() and
            super(User, self).is_authenticated
        )

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, id):
        self._id = id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def email_address(self):
        return self._email_address

    @email_address.setter
    def email_address(self, email_address):
        self._email_address = email_address

    @property
    def mobile_number(self):
        return self._mobile_number

    @mobile_number.setter
    def mobile_number(self, mobile_number):
        self._mobile_number = mobile_number

    @property
    def password_changed_at(self):
        return self._password_changed_at

    @password_changed_at.setter
    def password_changed_at(self, password_changed_at):
        self._password_changed_at = password_changed_at

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state

    @property
    def permissions(self):
        return self._permissions

    @permissions.setter
    def permissions(self, permissions):
        raise AttributeError("Read only property")

    def has_permissions(self, *permissions, any_=False, admin_override=False):

        unknown_permissions = set(permissions) - all_permissions

        if unknown_permissions:
            raise TypeError('{} are not valid permissions'.format(list(unknown_permissions)))

        # Only available to the platform admin user
        if admin_override and self.platform_admin:
            return True
        # Not available to the non platform admin users.
        # For example the list all-services page is only available to platform admin users and is not service specific
        if admin_override and not permissions:
            return False

        # Service id is always set on the request for service specific views.
        service_id = _get_service_id_from_view_args()
        if service_id in self._permissions:
            if any_:
                return any([x in self._permissions[service_id] for x in permissions])
            return set(self._permissions[service_id]) >= set(permissions)
        return False

    @property
    def auth_type(self):
        return self._auth_type

    @auth_type.setter
    def auth_type(self, auth_type):
        self._auth_type = auth_type

    @property
    def failed_login_count(self):
        return self._failed_login_count

    @failed_login_count.setter
    def failed_login_count(self, num):
        self._failed_login_count += num

    def is_locked(self):
        return self.failed_login_count >= self.max_failed_login_count

    def serialize(self):
        dct = {
            "id": self.id,
            "name": self.name,
            "email_address": self.email_address,
            "mobile_number": self.mobile_number,
            "password_changed_at": self.password_changed_at,
            "state": self.state,
            "failed_login_count": self.failed_login_count,
            "permissions": [x for x in self._permissions],
            "organisations": self.organisations,
            "current_session_id": self.current_session_id
        }
        if hasattr(self, '_password'):
            dct['password'] = self._password
        return dct

    def set_password(self, pwd):
        self._password = pwd

    @property
    def organisations(self):
        return self._organisations


class InvitedUser(object):

    def __init__(self, id, service, from_user, email_address, permissions, status, created_at, auth_type):
        self.id = id
        self.service = str(service)
        self.from_user = from_user
        self.email_address = email_address
        if isinstance(permissions, list):
            self.permissions = permissions
        else:
            if permissions:
                self.permissions = permissions.split(',')
            else:
                self.permissions = []
        self.status = status
        self.created_at = created_at
        self.auth_type = auth_type

    def has_permissions(self, *permissions):
        if self.status == 'cancelled':
            return False
        return set(self.permissions) > set(permissions)

    def __eq__(self, other):
        return ((self.id,
                self.service,
                self.from_user,
                self.email_address,
                self.auth_type,
                self.status) == (other.id,
                other.service,
                other.from_user,
                other.email_address,
                other.auth_type,
                other.status))

    def serialize(self, permissions_as_string=False):
        data = {'id': self.id,
                'service': self.service,
                'from_user': self.from_user,
                'email_address': self.email_address,
                'status': self.status,
                'created_at': str(self.created_at),
                'auth_type': self.auth_type
                }
        if permissions_as_string:
            data['permissions'] = ','.join(self.permissions)
        else:
            data['permissions'] = self.permissions
        return data


class InvitedOrgUser(object):

    def __init__(self, id, organisation, invited_by, email_address, status, created_at):
        self.id = id
        self.organisation = str(organisation)
        self.invited_by = invited_by
        self.email_address = email_address
        self.status = status
        self.created_at = created_at

    def __eq__(self, other):
        return ((self.id,
                self.organisation,
                self.invited_by,
                self.email_address,
                self.status) == (other.id,
                other.organisation,
                other.invited_by,
                other.email_address,
                other.status))

    def serialize(self, permissions_as_string=False):
        data = {'id': self.id,
                'organisation': self.organisation,
                'invited_by': self.invited_by,
                'email_address': self.email_address,
                'status': self.status,
                'created_at': str(self.created_at)
                }
        return data


class AnonymousUser(AnonymousUserMixin):
    # set the anonymous user so that if a new browser hits us we don't error http://stackoverflow.com/a/19275188
    def logged_in_elsewhere(self):
        return False
