# Sopel IdleRPG

A rewrite of the original [IdleRPG](http://idlerpg.net/) to work as a module for Sopel. It incorporates some of the features of [Shocky](https://github.com/clone1018/Shocky)'s IdleRPG system, though is much more in-depth.


### Getting Started


When Sopel joins a channel for the first time, IdleRPG will be disabled. A channel operator (+0) will have to use `.idlerpg start` to begin the IdleRPG. If at any time, a channel operator would like IdleRPG to pause, they can simply use `.idlerpg pause`. You may resume from a paused state with either `.idlerpg start` or `.idlerpg resume`.

In order for a channel user to participate in the IdleRPG, they must be authenticated with nickserv and type `>` or `>status` in the channel. If they are not authenticated, they will be warned that they must authenticate to participate in IdleRPG.

```
<+salty> >
-Sopel- [idlerpg] Welcome to IdleRPG, salty! You are logged in as maxpowa.
```

### Status

Players may check their status by sending `>` in a channel with IdleRPG enabled. Players must type `>` in order to level up.

Sopel will reply to these messages with a notice directly to the player.

Players may use any subset of characters to spell out `status` after the `>` as well, for example: `>stat`. Players are able to check other players' status by simply adding the other player's name after the `>status`, for example: `>stat salty`.

If you are using a nick which is different from your account name, you will see your name in the format `nick / account`.

```
<+salty> >s
-Sopel- [idlerpg] salty / maxpowa, level 27, XP: 28,054 / 77,727 (38,281 + 39,446) [=======          ] (36.1%) | 13h 47m 53s until level up
```

### Leaderboards

Players may view the leaderboard by typing `>leaderboards`, where again, they may use any subset characters of `leaderboards`. 

The leaderboard will show, at most, the top 10 idlers in the channel. If there are fewer than 10 people who have started their IdleRPG, only those people will be shown. Online players will have their nick shown in this list, but offline players will have their account name shown here.

```
<+salty> >l
-Sopel- 1. salty, level 27, XP: 28,187 / 77,727 (38,281 + 39,446) [=======          ] (36.3%)
-Sopel- 2. Soni, level 18, XP: 8,251 / 10,384 (10,066 + 318) [===============  ] (79.5%)
-Sopel- 3. Teh_Colt, level 16, level up available
-Sopel- 4. Assistant, level 12, level up available
```

### Penalties

Nearly every action you perform as a user may incur a penalty towards your next level. Penalty shorthand is p[num].

| Action           | Penalty           |
| ---------------: | ----------------- |
| Nick change      | p30               |
| Part             | p200              |
| Quit             | p20               |
| LOGOUT command   | p20               |
| Being Kicked     | p250              |
| Channel privmsg  | p[message_length] |
| Channel notice   | p[message_length] |

Penalties affect the amount of time it will take you to reach the next level. The penalties are applied as `NUM*(1.14^(YOUR_LEVEL))`, so a quit (p20) at level 10 will mean an additional 74 seconds (`20*(1.14^(10))`) towards your next level. Netsplit users are excluded from the quit penalty. 

###### TODO: The penalty formula may be adjusted by changing the config option xxx

Penalties are represented on your status in the parentheses following your XP. For example, in the below snippet the user `salty` has `39,446` seconds extra worth of penalties.

```
<+salty> >s
-Sopel- [idlerpg] salty / maxpowa, level 27, XP: 28,054 / 77,727 (38,281 + 39,446) [=======          ] (36.1%) | 13h 47m 53s until level up
```


### Items

TODO

### Battles

TODO

### Installation

The easy (and recommended) way: `pip install sopel_modules.idlerpg`

The less-easy way, you must already have Sopel installed to use this method.
```
git clone https://github.com/maxpowa/sopel-idlerpg
cd sopel-idlerpg
pip install .
```
