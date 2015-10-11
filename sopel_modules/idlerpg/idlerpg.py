# coding=utf-8

from __future__ import unicode_literals, absolute_import, division, print_function

from sopel import module,loader


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


@module.commands('auth')
def auth(bot, trigger):
    def callback(nick, auth):
        if (auth):
            bot.say('You win a potato!')
        else:
            bot.say('You must be authenticated with NickServ')

    check_auth(bot, trigger, callback)
