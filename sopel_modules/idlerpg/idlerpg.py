# coding=utf-8

from __future__ import unicode_literals, absolute_import, division, print_function

from sopel import module
from sopel.logger import get_logger
import idlerpg
from idlerpg.helpers import Session, Player

import re
import json
import math
import time
import sys

if sys.version_info.major < 3:
    str = unicode
    int = long
    range = xrange

LOGGER = get_logger(__name__)

netsplit_regex = re.compile('^:\S+\.\S+ \S+\.\S+$')
all_sessions = set()
flag = False


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


    if (trigger.group(2).strip().lower() == 'resume' or
            trigger.group(2).strip().lower() == 'start'):
        bot.db.set_channel_value(trigger.sender, 'idlerpg', True)
        # add sessions
        for nick in bot.channels[trigger.sender].users:
            user = bot.users[nick]
            LOGGER.info(repr(user))
            if user.nick.lower() == bot.config.core.nick.lower():
                continue
            if user.account == '0':
                continue

            session = Session(trigger.sender, user.nick, user.account)
            player = get_player(bot, session, session.login)
            if player is None:
                continue
            all_sessions.add(session)
            player.session = session
            player.update(None)
            save_player(bot, player)
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

    if not trigger.account or trigger.account == '0':
        return bot.notice('[idlerpg] You must be authenticated with '
            'NickServ', destination=trigger.nick)

    session = Session(trigger.sender, trigger.nick, trigger.account)
    all_sessions.add(session)

    args = trigger.args[1:]
    args = args[0][1:].strip().split(' ')
    if len(args[0]) == 0 and len(args) == 1:
        args = []
    elif len(args[0]) == 0:
        return  # This must be an unrelated > prefixed message
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
@module.priority('low')
def join(bot, trigger):
    if not bot.db.get_channel_value(trigger.sender, 'idlerpg'):
        return

    if not trigger.account:
        return
    session = Session(trigger.sender, trigger.nick, trigger.account)
    player = get_player(bot, session, session.login)
    if player is None:
        return
    all_sessions.add(session)
    player.session = session
    player.update(None)
    save_player(bot, player)


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
