# coding=utf-8

from __future__ import unicode_literals, absolute_import, division, print_function

from sopel import module,loader

import json
import math
import time
import sys

if sys.version_info.major < 3:
    str = unicode
    int = long
    range = xrange


current_milli_time = lambda: int(round(time.time() * 1000))
current_sec_time = lambda: int(round(time.time()))

def _pretty_delta(delta):
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


class Session:
    def __init__(self, channel=None, nick=None, login=None):
        self.channel = channel
        self.nick = nick
        self.login = login


    def get_data(self):
        return {
            'channel': self.channel,
            'nick': self.nick,
            'login': self.login
        }


xp_table = {}
class Player:
    def __init__(self, session=None, level=1, xp=0, last_update=None):
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


    def get_data(self):
        return {
            'session': self.session.get_data(),
            'level': self.level, 
            'xp': self.xp,
            'last_update': self.last_update
        }


    def get_xp_for(self, level):
        global xp_table
        try:
            level = int(level)
        except ValueError:
            raise ValueError('get_xp_for(%s) failed'.format(str(level)))
        if level <= 1:
            return 0
        if level in xp_table:
            return xp_table[level]
        a = 0
        for x in range(1, level):
            a += int(x + 300.0 * math.pow(2, x / 7))
        value = math.ceil(a / 4.0)
        xp_table[level] = value
        return value


    def xp_to_next_level(self):
        return self.get_xp_for(self.level + 1)


    def get_progress_bar(self, value, length):
        percent = 1.0 / length
        bar = '['
        for i in range(1, length - 2):
            bar += ('=' if (value >= i * percent) else ' ')
        return bar + ']'


    def update(self, session):
        time = current_sec_time()
        diff = time - self.last_update
        self.last_update = time

        xp_for_next = self.xp_to_next_level()
        self.xp += diff
        if (session is not None and session.login == self.session.login and
                self.xp >= xp_for_next):
            self.xp = 0
            self.level += 1

        if self.xp > xp_for_next:
            self.xp = xp_for_next


    def get_status(self, bot, session, include_xp=False, include_time=False):
        response = session.nick
        if (session.login == self.session.login and
                session.nick != session.login):
            response += ' / ' + self.session.login
        response += ', level ' + str(self.level)

        target_xp = self.xp_to_next_level()
        if include_xp:
            if self.level is not 1 and self.xp is 0:
                response += ', LEVEL UP!'

                if (self.level % 5) is 0:
                    congrats = '>>> CONGRATULATIONS!'
                    if (session.login is self.session.login and
                            session.nick is not session.login):
                        congrats += ' / ' + session.nick
                    congrats += ' achieved level ' + str(self.level) + '! <<<'
                    bot.say(congrats)
            elif self.xp == target_xp:
                response += ', level up available'
            else:
                response += ', XP: {:,} / {:,}'.format(self.xp, target_xp)

            if self.xp > 0 and self.xp < target_xp:
                response += ' '
                response += self.get_progress_bar(self.xp / target_xp, 20)
                response += ' ({:.1%}%)'.format(self.xp / target_xp)

        if include_time and self.xp is not target_xp:
            response += ' | {} until level up'.format(
                _pretty_delta(target_xp - self.xp))

        return response


def configure(config):
    pass


def setup(bot):
    pass


flag = False

def perform_who(bot, trigger, nick=None, success=None, fail=None):
    @module.rule('.*')
    @module.priority('low')
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


def create_player(bot, session):
    data = Player(session).get_data()
    bot.db.set_nick_value(session.login, 'idlerpg_' + session.channel, data)


def get_player(bot, session, nick):
    data = bot.db.get_nick_value(nick, 'idlerpg_' + session.channel)
    if not data:
        return None
    return Player(**data)


def save_player(bot, player):
    data = player.get_data()
    bot.db.set_nick_value(player.session.login, 'idlerpg_' + 
        player.session.channel, data)
    users = bot.db.get_channel_value(player.session.channel, 'idlerpg_players')
    if not users:
        users = []
    if player.session.login not in users:
        users.append(player.session.login)
        bot.db.set_channel_value(player.session.channel, 'idlerpg_players', 
            users)


@module.rule('.*')
@module.event('PRIVMSG')
def auth(bot, trigger):
    if not trigger.args[1].startswith('>'):
        return

    if False and not bot.db.get_channel_value(trigger.sender, 'idlerpg'):
        return


    def callback(nick, auth):
        if not auth:
            return bot.say('[idlerpg] You must be authenticated with NickServ')

        session = Session(trigger.sender, trigger.nick, auth)

        args = trigger.args[1:]
        args = args[0][1:].split(' ')
        if len(args[0]) == 0:
            args = []
        if len(args) == 0 or (len(args) <= 2 
            and 'status'.startswith(args[0].lower())):

            check = get_player(bot, session, session.login)
            if (len(args) == 2):
                check = get_player(bot, session, args[1])

            if check is None:
                if (len(args) == 2):
                    return bot.notice('[idlerpg] Player \'{}\' does not exist.'
                        .format(args[1]), destination=trigger.nick)
                create_player(bot, session)
                return bot.notice('[idlerpg] Welcome to IdleRPG, {}! You are '
                    'logged in as {}.'.format(session.nick, session.login),
                    destination=trigger.nick)

            check.update(session)
            save_player(bot, check)
            bot.notice('[idlerpg] {}'.format(check.get_status(bot, session, 
                include_xp=True, include_time=True)), destination=trigger.nick)
        elif len(args) == 1 and 'leaderboards'.startswith(args[0].lower()):
            name_list = bot.db.get_channel_value(session.channel, 
                'idlerpg_players')
            if not name_list:
                name_list = []
            player_list = []
            for name in name_list:
                player = get_player(bot, session, name)
                player.update(player.session)
                save_player(bot, player)
                player_list.append(player)
            player_list.sort(key=lambda x: (x.level, x.xp), reverse=False)
            #TODO: Config leaderboard print amount
            size = 10 if (len(player_list) >= 10) else len(player_list)
            out = ''
            for i in range(0, size):
                player = player_list[i]
                out = '{}. {}'.format(str(i + 1), player.get_status(bot, 
                    session, include_xp=True))
                bot.notice(out, destination=trigger.nick)
            
    check_auth(bot, trigger, callback)


