#!/usr/bin/env python
"""User-related views."""

import helpers
import libunison.password as password
import libunison.mail as mail
import storm.exceptions

from constants import errors, events
from flask import Blueprint, request, g, jsonify
from libunison.models import User, Group, Track, LibEntry, GroupEvent


user_views = Blueprint('user_views', __name__)


@user_views.route('', methods=['POST'])
def register_user():
    """Register a new user."""
    try:
        email = request.form['email']
        pw = request.form['password']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing e-mail and / or password")
    # Check that there is no user with that e-mail address.
    if g.store.find(User, User.email == email).one() is not None:
        raise helpers.BadRequest(errors.EXISTING_USER,
                "user already exists")
    # Check that the e-mail address is valid.
    elif not mail.is_valid(email):
        raise helpers.BadRequest(errors.INVALID_EMAIL,
                "e-mail is not valid")
    # Check that the password is good enough.
    elif not password.is_good_enough(pw):
        raise helpers.BadRequest(errors.INVALID_PASSWORD,
                "password is not satisfactory")
    # All the checks went through, we can create the user.
    user = User(email, password.encrypt(pw))
    g.store.add(user)
    g.store.flush()  # Necessary to get an ID.
    # Default nickname.
    user.nickname = unicode("user%d" % user.id)
    return jsonify(uid=user.id)


@user_views.route('/<int:uid>/nickname', methods=['GET'])
@helpers.authenticate()
def get_user_nickname(uid):
    """Get any user's nickname."""
    user = g.store.get(User, uid)
    if user is None:
        raise helpers.BadRequest(errors.INVALID_USER,
                "user does not exist")
    return jsonify(uid=user.id, nickname=user.nickname)


@user_views.route('/<int:uid>/nickname', methods=['PUT'])
@helpers.authenticate(with_user=True)
def update_user_nickname(user, uid):
    """Assign a nickname to the user."""
    helpers.ensure_users_match(user, uid)
    try:
        user.nickname = request.form['nickname']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing nickname")
    return helpers.success()


@user_views.route('/<int:uid>/email', methods=['PUT'])
@helpers.authenticate(with_user=True)
def update_user_email(user, uid):
    """Update the user's e-mail address."""
    helpers.ensure_users_match(user, uid)
    try:
        email = request.form['email']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing e-mail address")
    if not mail.is_valid(email):
        raise helpers.BadRequest(errors.INVALID_EMAIL,
                "e-mail is not valid")
    try:
        user.email = email
        g.store.flush()
    except storm.exceptions.IntegrityError:
        # E-mail already in database.
        raise helpers.BadRequest(errors.EXISTING_USER,
                "e-mail already taken by another user")
    return helpers.success()


@user_views.route('/<int:uid>/password', methods=['PUT'])
@helpers.authenticate(with_user=True)
def update_user_password(user, uid):
    """Update the user's password."""
    helpers.ensure_users_match(user, uid)
    try:
        pw = request.form['password']
    except KeyError:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "missing password")
    if not password.is_good_enough(pw):
        raise helpers.BadRequest(errors.INVALID_EMAIL,
                "password is not satisfactory")
    user.password = password.encrypt(pw)
    return helpers.success()


@user_views.route('/<int:uid>/group', methods=['PUT', 'DELETE'])
@helpers.authenticate(with_user=True)
def update_user_group(user, uid):
    """Join or leave a group."""
    helpers.ensure_users_match(user, uid)
    if request.method == 'DELETE':
        if user.group is not None:
            if user.group.master == user:
                user.group.master = None
            event = GroupEvent(user.group, user, events.LEAVE, None)
            g.store.add(event)
        user.group = None
        return helpers.success()
    try:
        gid = int(request.form['gid'])
    except:
        raise helpers.BadRequest(errors.MISSING_FIELD,
                "cannot to parse group ID")
    group = g.store.get(Group, gid)
    if group is None:
        raise helpers.BadRequest(errors.INVALID_GROUP,
                "group does not exist")
    if user.group != group:
        if user.group is not None:
            if user.group.master == user:
                # The user was his old group's master.
                user.group.master == None
            event = GroupEvent(user.group, user, events.LEAVE, None)
            g.store.add(event)
        user.group = group
        event = GroupEvent(group, user, events.JOIN, None)
        g.store.add(event)
    return helpers.success()
