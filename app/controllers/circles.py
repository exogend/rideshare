from app.common.toolbox import doRender, split_address, grab_json
from google.appengine.ext import db
from app.model import *
import datetime
from datetime import date
from app.base_handler import BaseHandler
from app.common.voluptuous import *
from app.common.notification import push_noti
import json
import re

class EditCircle(BaseHandler):
    def get(self, circle_id):
        self.auth()

        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        if not circle:
            self.redirect('/circles')

        properties = ['name', 'description', 'privacy', 'permission', 'color']

        circle_json = grab_json(circle, properties)
        
        doRender(self, 'edit_circle.html', {
            'user': user,
            'circle': circle,
            'circle_json': circle_json
        })
    def post (self, circle_id):
        self.auth()

        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        if not circle:
            self.resp_json(500, {
                'message': 'Circle not found.'
            })

        circle_schema = Schema({
            Required('name'): All(unicode, Length(min=3)),
            Required('description', default=""): unicode,
            Required('privacy', default="public"): unicode,
            Required('color', default="#607d8b"): unicode,
            Required('permission'): unicode
        })

        json_str = self.request.body
        data = json.loads(json_str)

        try:
            circle_schema(data)
        except MultipleInvalid as e:
            print str(e)
            self.response.set_status(500)
            self.response.write(json.dumps({
                    'error': str(e),
                    'message': 'Data could not be validated'
                }))
            return None

        circle.name = data['name']
        circle.description = data['description']
        circle.privacy = data['privacy']
        circle.color = data['color']
        circle.permission = data['permission']

        circle.put()

        self.response.write(json.dumps({
            'message': 'Circle edited!',
            'id': circle.key().id()
        }))

class GetCircleHandler(BaseHandler):
    def get(self, circle_id):
        self.auth()

        circle = Circle.get_by_id(int(circle_id))

        if not circle:
            self.redirect('/circles')
            return None

        user = self.current_user()

        # Grabs members
        members = User.all().filter('circles = ', circle.key()).fetch(100)

        requests = User.all().filter('__key__ in', circle.requests).fetch(100)

        notis = Notification.all().filter('circle = ', circle.key()).filter('type = ', 'circle_message').fetch(100)

        for noti in notis:
            noti.date_str = noti.created.strftime('%B %dth, %Y')

        if circle.key() in user.circles:
            has_permission = True
        else:
            has_permission = False

        invite = Invite.all().filter('circle = ', circle.key()).filter('user = ', user.key()).get()

        if invite:
            has_permission = True

        if not has_permission:
            self.redirect('/circles')
            return None

        if user.key() in circle.admins:
            is_admin = True
        else:
            is_admin = False

        today = date.today()

        events_all = Event.all().filter('circle =', circle).filter('date >=', today).fetch(None)

        doRender(self, 'view_circle.html', {
            'circle': circle,
            'user': user,
            'members': members,
            'invite': invite,
            'is_admin': is_admin,
            'requests': requests,
            'notis': notis,
            'events_all': events_all
        })

class CircleInvited(BaseHandler):
    def get(self, circle_id):
        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        doRender(self, 'view_invite_circle.html', {
            'user': user,
            'circle': circle
        })


class GetCircleInvite(BaseHandler):
    def get(self, circle_id):
        self.auth()

        circle = Circle.get_by_id(int(circle_id))

        user = self.current_user()

        doRender(self, 'view_circle_invite.html', {
            'circle': circle,
            'user': user
        })

class CircleHandler(BaseHandler):
    def get(self):
        self.auth()
        user = self.current_user()

        circles = Circle.all().filter('privacy !=', 'invisible').fetch(100)

        for circle in circles:
            if circle.key() in user.circles:
                circle.user = True
            else:
                circle.user = False

        doRender(self, 'circles.html', {
            'circles': circles,
            'user': user
        })
    def post(self):
        self.auth()

        user = self.current_user()

        circle = Circle()

        circle_schema = Schema({
            Required('name'): All(unicode, Length(min=3)),
            Required('description', default=""): unicode,
            Required('privacy', default="public"): unicode,
            Required('color', default="#607d8b"): unicode,
            Required('permission'): unicode
        })

        json_str = self.request.body
        data = json.loads(json_str)

        try:
            circle_schema(data)
        except MultipleInvalid as e:
            return self.json_resp(500, {
                'error': str(e),
                'message': 'Data could not be validated'
            })

        circle.name = data['name']
        circle.description = data['description']
        circle.privacy = data['privacy']
        circle.color = data['color']
        circle.permission = data['permission']
        circle.admins.append(user.key())

        circle.put()

        user.circles.append(circle.key())

        user.put()

        self.response.write(json.dumps({
            'message': 'Circle created!',
            'id': circle.key().id()
        }))

class JoinCircle(BaseHandler):
    def post(self):
        self.auth()

        user = self.current_user()

        json_str = self.request.body
        data = json.loads(json_str)

        if user:
            circle_id = int(data['circle'])
            circle_key = Circle.get_by_id(circle_id).key()
            if data['action'] == 'add':
                if circle_key not in user.circles:
                    user.circles.append(circle_key)
            elif data['action'] == 'remove':
                if circle_key in user.circles:
                    user.circles.remove(circle_key)

            user.put()
        else:
            self.response.set_status(500)

class NewCircleHandler(BaseHandler): # actual page
    def get(self):
        self.auth()

        user = self.current_user()

        doRender(self, "newCircle.html", {
            "user": user
        })

class ChangeCircle(BaseHandler):
    def get(self, circle_id):
        self.auth()

        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        if not circle:
            self.session['circle'] = None
        else:
            self.session['circle'] = circle.key().id()

        self.redirect('/circle/' + str(circle.key().id()))

class KickMember(BaseHandler):
    def post(self, circle_id):
        self.auth()

        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        if not circle:
            return self.json_resp(500, {
                'message': 'Circle does not exist'
            })

        json_str = self.request.body
        data = json.loads(json_str)

        user = User.get_by_id(data['user'])

        if not user:
            return self.json_resp(500, {
                'message': 'User does not exist'
            })

        if circle.key().id() in user.circles:
            user.circles.remove(circle.key().id())

        user.put()

        return self.json_resp(200, {
            'message': 'Member kicked'
        })

class PromoteMember(BaseHandler):
    def post(self, circle_id):
        self.auth()

        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        if not circle:
            return self.json_resp(500, {
                'message': 'Circle does not exist'
            })

        json_str = self.request.body
        data = json.loads(json_str)

        user = User.get_by_id(data['user'])

        if not user:
            return self.json_resp(500, {
                'message': 'User does not exist'
            })

        if user.key().id() in circle.admins:
            circle.admins.remove(user.key().id())

        circle.put()

        return self.json_resp(200, {
            'message': 'Member promoted'
        })

class RequestJoin(BaseHandler):
    def post(self, circle_id):
        self.auth()

        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        if not circle:
            return self.json_resp(500, {
                'message': 'Circle does not exist'
            })

        circle.requests.append(user.key())

        circle.put()

        for admin in circle.admins:
            noti = Notification()
            noti.type = 'request'
            noti.user = admin
            noti.circle = circle.key()
            noti.put()

        return self.json_resp(200, {
            'message': 'Request sent'
        })

class RequestAccept(BaseHandler):
    def post(self, circle_id):
        self.auth()

        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        if user.key() not in circle.admins:
            return self.json_resp(500, {
                'message': 'You do not have permission for this.'
            })

        if not circle:
            return self.json_resp(500, {
                'message': 'Circle does not exist'
            })

        json_str = self.request.body
        data = json.loads(json_str)

        requester = User.get_by_id(int(data['user']))

        if circle.key() not in requester.circles:
            requester.circles.append(circle.key())
            requester.put()

        if requester.key() in circle.requests:
            circle.requests.remove(requester.key())
            circle.put()

        return self.json_resp(200, {
            'message': 'Request accepted'
        })

class CircleMessage(BaseHandler):
    def post(self, circle_id):
        self.auth()

        user = self.current_user()

        circle = Circle.get_by_id(int(circle_id))

        if user.key() not in circle.admins:
            return self.json_resp(500, {
                'message': 'You do not have permission for this.'
            })

        if not circle:
            return self.json_resp(500, {
                'message': 'Circle does not exist'
            })

        json_str = self.request.body
        data = json.loads(json_str)

        members = User.all().filter('circle = ', circle.key()).fetch(100)

        for member in members:
            noti = Notification()
            noti.user = user.key()
            noti.circle = circle.key()
            noti.type = 'circle_message'
            noti.text = data['message']
            noti.put()

        for admin in circle.admins:
            noti = Notification()
            noti.user = admin
            noti.circle = circle.key()
            noti.type = 'circle_message'
            noti.text = data['message']
            noti.put()

        return self.json_resp(200, {
            'message': 'Message sent to all users'
        })