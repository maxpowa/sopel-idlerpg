# coding=utf-8

from __future__ import unicode_literals, absolute_import, division, print_function

from sopel import module,loader
import idlerpg

import re
import json
import math
import time
import sys

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

current_milli_time = lambda: int(round(time.time() * 1000))
current_sec_time = lambda: int(round(time.time()))

netsplit_regex = re.compile('^:\S+\.\S+ \S+\.\S+$')
all_sessions = set()
flag = False


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
                _pretty_delta(target_xp - self.xp))

        return response


    def penalize(self, penalty):
        self.penalties += penalty


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


def create_player(bot, session):
    data = Player(session).get_data()
    bot.db.set_nick_value(session.login, 'idlerpg_' + session.channel, data)


def get_player(bot, session, login):
    for s in all_sessions:
        if (s.nick.lower() == login.lower() or 
                s.login.lower() == login.lower()):
            login = s.login
            break
    data = bot.db.get_nick_value(login, 'idlerpg_' + session.channel)
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


@module.commands('idlerpg', 'irpg')
@module.require_chanmsg('[idlerpg] You can\'t configure idlerpg in a '
                        'private message!')
@module.require_privilege(module.OP, '[idlerpg] You must be an OP to '
                          'change idlerpg settings!')
@module.priority('low')
def ch_settings(bot, trigger):
    """
    .irpg <start|resume|pause> - Resume or pause idlerpg in the current channel
    """
    global all_sessions
    if not trigger.group(2):
        bot.say(ch_settings.__doc__)
        return

    def success(b, t):
        if t.args[1].lower() == bot.config.core.nick.lower():
            return
        if t.args[2] != '0':
            session = Session(trigger.sender, t.args[1], t.args[2])
            player = get_player(bot, session, session.login)
            if player is None:
                return
            all_sessions.add(session)
            player.session = session
            player.update(None)
            save_player(bot, player)

    if (trigger.group(2).strip().lower() == 'resume' or 
            trigger.group(2).strip().lower() == 'start'):
        bot.db.set_channel_value(trigger.sender, 'idlerpg', True)
        perform_who(bot, trigger, nick=trigger.sender,
            success=success)
        bot.say('[idlerpg] Resuming idlerpg in ' + trigger.sender)
    elif ('version'.startswith(trigger.group(2).strip().lower())):
        bot.say('[idlerpg] Version {} by {}, report issues at {}'.format(
            idlerpg.__version__, idlerpg.__author__, idlerpg.__repo__)) 
    else:
        bot.db.set_channel_value(trigger.sender, 'idlerpg', False)
        new_sessions = set()
        for session in all_sessions:
            if session.channel == trigger.sender:
                continue
            new_sessions.add(session)
        all_sessions = new_sessions
        bot.say('[idlerpg] Paused idlerpg in ' + trigger.sender)


@module.rule('^>.*')
@module.event('PRIVMSG')
@module.require_chanmsg('[idlerpg] You must play idlerpg with other people!')
@module.priority('low')
@module.thread(True)
def auth(bot, trigger):
    if not bot.db.get_channel_value(trigger.sender, 'idlerpg'):
        return

    def callback(nick, auth):
        if not auth or auth == '0':
            return bot.notice('[idlerpg] You must be authenticated with '
                'NickServ', destination=trigger.nick)

        session = Session(trigger.sender, trigger.nick, auth)
        all_sessions.add(session)

        args = trigger.args[1:]
        args = args[0][1:].strip().split(' ')
        if len(args[0]) == 0 and len(args) == 1:
            args = []
        elif len(args[0]) == 0:
            return # This must be an unrelated > prefixed message
        if len(args) == 0 or (len(args) <= 2 and 
                'status'.startswith(args[0].lower())):

            check = get_player(bot, session, session.login)
            if (len(args) == 2):
                check = get_player(bot, session, args[1])

            if check is None:
                if (len(args) == 2):
                    return bot.notice('[idlerpg] Player \'{}\' does not exist.'
                        .format(args[1]), destination=trigger.nick)
                create_player(bot, session)
                all_sessions.add(session)
                return bot.notice('[idlerpg] Welcome to IdleRPG, {}! You are '
                    'logged in as {}.'.format(session.nick, session.login),
                    destination=trigger.nick)

            check.update(session)
            save_player(bot, check)
            bot.notice('[idlerpg] {}'.format(check.get_status(bot, session, 
                include_xp=True, include_time=True)), destination=trigger.nick)
        elif len(args) == 1 and 'leaderboards'.startswith(args[0].lower()):
            player_list = []
            name_list = bot.db.get_channel_value(trigger.sender, 'idlerpg_players')
            if not name_list:
                name_list = []
            for login in name_list:
                session = Session(trigger.sender, login, login)
                player = get_player(bot, session, session.login)
                if not player:
                    continue
                tmp = Session(session.channel, '', '')
                player.update(tmp)
                player_list.append(player)
            player_list.sort(key=lambda x: (x.level, x.xp / 
                (x.xp_to_next_level() + x.get_penalty_time())), reverse=True)
            #TODO: Config leaderboard print amount
            size = 10 if (len(player_list) >= 10) else len(player_list)
            out = ''
            for i in range(0, size):
                player = player_list[i]
                out = '{}. {}'.format(str(i + 1), player.get_status(bot, 
                    session, include_xp=True, leaderboard=True))
                bot.notice(out, destination=trigger.nick)

    for session in all_sessions:
        if (trigger.nick == session.nick):
            callback(session.nick, session.login)
            break
    else:
        check_auth(bot, trigger, callback)


@module.interval(60)
def update_all(bot):
    for session in all_sessions:
        if not bot.db.get_channel_value(session.channel, 'idlerpg'):
            continue
        player = get_player(bot, session, session.login)
        if player is None:
            continue
        # Fake session to updaate players with
        s = Session(session.channel, '', '')
        player.update(s)
        save_player(bot, player)


@module.rule('^[^.>].*')
def privmsg(bot, trigger):
    for session in all_sessions:
        if session.channel != trigger.sender or trigger.nick != session.nick:
            continue
        player = get_player(bot, session, session.login)
        if player is None:
            continue
        player.session = session
        player.penalize(len(trigger.match.string))
        player.update(session)
        save_player(bot, player)


@module.rule('.*')
@module.event('NOTICE')
def notice(bot, trigger):
    for session in all_sessions:
        if session.channel != trigger.sender or trigger.nick != session.nick:
            continue
        player = get_player(bot, session, session.login)
        if player is None:
            continue
        player.session = session
        player.penalize(len(trigger.match.string))
        player.update(session)
        save_player(bot, player)


@module.rule('.*')
@module.event('JOIN')
def join(bot, trigger):
    if not bot.db.get_channel_value(trigger.sender, 'idlerpg'):
        return

    def success(b, t):
        if t.args[1].lower() == bot.config.core.nick.lower():
            return
        if t.args[2] != '0':
            session = Session(trigger.sender, t.args[1], t.args[2])
            player = get_player(bot, session, session.login)
            if player is None:
                return
            all_sessions.add(session)
            player.session = session
            player.update(None)
            save_player(bot, player)


    if trigger.nick.lower() == bot.config.core.nick.lower():
        #We are joining a channel, enumerate users.
        perform_who(bot, trigger, nick=trigger.sender, 
            success=success)
        return


    def callback(nick, auth):
        if not auth:
            return
        session = Session(trigger.sender, trigger.nick, auth)
        player = get_player(bot, session, session.login)
        if player is None:
            return
        all_sessions.add(session)
        player.session = session
        player.update(None)
        save_player(bot, player)

    check_auth(bot, trigger, callback)


@module.rule('.*')
@module.event('QUIT')
@module.priority('high')
def quit(bot, trigger):
    global all_sessions
    netsplit = netsplit_regex.match(trigger.match.string)
    new_sessions = set()
    for session in all_sessions:
        if session.nick == trigger.nick:
            session = Session(session.channel, trigger.nick, session.login)
            player = get_player(bot, session, session.login)
            if player is None:
                continue
            player.session = session
            if netsplit:
                player.update(None)
            else:
                player.penalize(20)
                player.update(session)
            save_player(bot, player)
        else:
            new_sessions.add(session)
    all_sessions = new_sessions


@module.rule('.*')
@module.event('NICK')
@module.priority('high')
def nick(bot, trigger):
    global all_sessions
    new_sessions = set()
    for session in all_sessions:
        if session.nick == trigger.nick:
            session.nick = trigger.sender
        new_sessions.add(session)
        player = get_player(bot, session, session.login)
        if player is None:
            continue
        player.session = session
        player.penalize(30)
        player.update(session)
        save_player(bot, player)
    all_sessions = new_sessions


@module.rule('.*')
@module.event('PART')
@module.priority('high')
def part(bot, trigger):
    global all_sessions
    new_sessions = set()
    for session in all_sessions:
        if session.channel != trigger.sender or trigger.nick != session.nick:
            new_sessions.add(session)
            continue
        player = get_player(bot, session, session.login)
        if player is None:
            continue
        player.session = session
        player.penalize(200)
        player.update(session)
        save_player(bot, player)
    all_sessions = new_sessions


@module.rule('.*')
@module.event('KICK')
@module.priority('high')
def kick(bot, trigger):
    global all_sessions
    new_sessions = set()
    for session in all_sessions:
        if session.channel != trigger.sender or session.nick != trigger.args[1]:
            new_sessions.add(session)
            continue
        player = get_player(bot, session, session.login)
        if player is None:
            continue
        player.session = session
        player.penalize(250)
        player.update(session)
        save_player(bot, player)
    all_sessions = new_sessions
