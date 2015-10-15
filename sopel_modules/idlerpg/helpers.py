# coding=utf-8

from __future__ import unicode_literals, absolute_import, division, print_function

from sopel import module, loader
import sys
import math
import time

if sys.version_info.major < 3:
    str = unicode
    int = long
    range = xrange


""" Formula for the amount of time (in seconds) it takes to reach
    the given level """
LEVEL_FORMULA = lambda x: math.ceil(600 * math.pow(1.16, x))

""" Maximum level to use the standard level formula for """
HIGH_LEVEL = 60

""" Formula to use once users have surpassed the regular level formula """
HIGH_LEVEL_FORMULA = (lambda x: 
    math.ceil(LEVEL_FORMULA(HIGH_LEVEL) + (86400 * (x - HIGH_LEVEL))))

""" Formula to use when calculating additional time for penalties """
PENALTY_FORMULA = lambda x, y: math.ceil(x * (math.pow(1.14, y)))

current_sec_time = lambda: int(round(time.time()))

#TODO: Document these classes, test them
class Session:
    def __init__(self, channel=None, nick=None, login=None):
        self.channel = str(channel)
        self.nick = str(nick)
        self.login = str(login)


    def get_data(self):
        return {
            'channel': self.channel,
            'nick': self.nick,
            'login': self.login
        }


    def __str__(self):
        return str(self.get_data())


    def __repr__(self):
        return self.__str__()


    def __eq__(self, other):
        return self.channel == other.channel and self.login == other.login


    def __hash__(self):
        return hash((self.channel, self.login))


class Player:
    def __init__(self, session=None, level=1, xp=0, last_update=None, 
                 penalties=0):
        if not session:
            raise ValueError('Session is required to initialize player')
        if type(session) is dict:
            self.session = Session(**session)
        elif type(session) is Session:
            self.session = session
        else:
            raise ValueError('Session was an invalid object')
        self.level = level
        self.xp = xp
        self.last_update = last_update if last_update else current_sec_time()
        self.penalties = penalties


    def get_data(self):
        return {
            'session': self.session.get_data(),
            'level': self.level, 
            'xp': self.xp,
            'last_update': self.last_update,
            'penalties': self.penalties
        }


    def get_xp_for(self, level):
        try:
            level = int(level)
        except ValueError:
            raise ValueError('get_xp_for(%s) failed'.format(str(level)))
        if level <= 1:
            return 0
        if level < HIGH_LEVEL:
            value = LEVEL_FORMULA(level)
        else:
            value = HIGH_LEVEL_FORMULA(level)
        return value


    def xp_to_next_level(self):
        return self.get_xp_for(self.level + 1)


    def get_penalty_time(self):
        return PENALTY_FORMULA(self.penalties, self.level) 


    def get_progress_bar(self, value, length):
        percent = 1.0 / length
        bar = '['
        for i in range(1, length - 2):
            bar += ('=' if (value >= i * percent) else ' ')
        return bar + ']'


    def update(self, session):
        if (session is None):
            self.last_update = current_sec_time()
            return

        time = current_sec_time()
        diff = time - self.last_update
        self.last_update = time

        xp_for_next = self.xp_to_next_level() + self.get_penalty_time()
        self.xp += diff
        if (session.login == self.session.login and self.xp >= xp_for_next):
            self.session = session
            self.xp = 0
            self.level += 1
            self.penalties = 0

        if self.xp > xp_for_next:
            self.xp = xp_for_next


    def get_status(self, bot, session, include_xp=False, include_time=False,
            leaderboard=False):
        response = session.nick 
        if session.login != self.session.login:
            response = self.session.nick
        if (session.login == self.session.login and
                session.nick != session.login):
            response += ' / ' + self.session.login
        response += ', level ' + str(self.level)

        target_xp = self.xp_to_next_level() + self.get_penalty_time()
        if include_xp:
            if (self.level is not 1 and self.xp is 0 and 
                    session.login == self.session.login and not leaderboard):
                response += ', LEVEL UP!'

                if (self.level % 5) is 0:
                    congrats = '>>> CONGRATULATIONS! ' + session.nick
                    if (session.login == self.session.login and
                            session.nick != session.login):
                        congrats += ' / ' + self.session.login
                    congrats += ' achieved level ' + str(self.level) + '! <<<'
                    bot.say(congrats)
            elif self.xp == target_xp or (leaderboard and self.xp == 0):
                response += ', level up available'
            else:
                if (target_xp == self.xp_to_next_level()):
                    response += ', XP: {:,} / {:,}'.format(self.xp, target_xp)
                else:
                    response += ', XP: {:,} / {:,} ({:,} + {:,})'.format(
                        self.xp, target_xp, self.xp_to_next_level(), 
                        self.get_penalty_time())

            if self.xp > 0 and self.xp < target_xp:
                response += ' '
                response += self.get_progress_bar(self.xp / target_xp, 20)
                response += ' ({:.1%})'.format(self.xp / target_xp)

        if include_time and self.xp is not target_xp:
            response += ' | {} until level up'.format(
                pretty_delta(target_xp - self.xp))

        return response


    def penalize(self, penalty):
        self.penalties += penalty


def pretty_delta(delta):
    if delta is 0:
        return 'now'

    s = int(delta % 60)
    delta /= 60
    m = int(delta % 60)
    delta /= 60
    h = int(delta % 24)
    delta /= 24
    d = int(delta % 7)
    delta /= 7
    w = int(delta % 52.175)
    delta /= 52.175
    y = int(delta)

    ret = ''
    if y > 0:
        ret += str(y) + 'y '
    if w > 0:
        ret += str(w) + 'w '
    if d > 0:
        ret += str(d) + 'd '
    if h > 0:
        ret += str(h) + 'h '
    if m > 0:
        ret += str(m) + 'm '
    if s > 0:
        ret += str(s) + 's'
    return ret


def perform_who(bot, trigger, nick=None, success=None, fail=None, end=None):
    @module.rule('.*')
    @module.priority('high')
    @module.event('354')
    def who_recv(b, t):
        global flag
        flag = True
        if success:
            success(b, t)


    @module.rule('.*')
    @module.priority('low')
    @module.event('315')
    def who_end(b, t):
        global flag
        if fail and not flag:
            fail(b, t)
        if end:
            end(b, t)
        flag = False
        bot.unregister(who_recv)
        bot.unregister(who_end)


    if not nick:
        nick = trigger.nick
    loader.clean_callable(who_recv, bot.config)
    loader.clean_callable(who_end, bot.config)
    meta = ([who_recv, who_end],[],[])
    bot.register(*meta)
    bot.write(['WHO', nick, '%na'])


def check_auth(bot, trigger, cb):
    def success(b, t):
        cb(t.args[1], t.args[2])


    def fail(b, t):
        cb(t.args[1], None)


    perform_who(bot, trigger, success=success, fail=fail)

