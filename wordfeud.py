# -*- coding: UTF-8 -*-
from UserDict import UserDict
from datetime import datetime
import Cookie
import bisect
import codecs
import itertools
import logging as log
import random
import string
import config


try:
    import json
    import urllib2
    appengine = False
except ImportError:
    from django.utils import simplejson as json
    from google.appengine.api import urlfetch
    from google.appengine.api import memcache
    appengine = True


def get_host():
    return 'game%02d.wordfeud.com' % random.randint(0, 5)

def get_base_url():
    return 'http://' + get_host() + '/wf/'

def post_json(action, json_data='', cookie=None):
    if cookie is None:
        cookie = Cookie.SimpleCookie()

    cookie_str = cookie.output(header='')
    headers = {'Content-type': 'application/json',
               'From': 'johanliesen@gmail.com',
               'Cookie': cookie_str}
    url = get_base_url() + action

    if appengine:
        resp = urlfetch.fetch(url, json_data, method='POST', headers=headers, deadline=30)
    else:
        req = urllib2.Request(url, json_data, headers=headers)
        resp = urllib2.urlopen(req)

    cookie_str = resp.headers.get('Set-Cookie', '')
    cookie.load(cookie_str)

    if appengine:
        try:
            return json.loads(resp.content), cookie
        except ValueError:
            log.error("Bad response: %s" % resp.content)
            raise
    else:
        return json.load(resp), cookie

def check_status(resp, f=None):
    if resp.get('status', 'error') == 'success':
        if f is not None:
            return f(resp.get('content'))

        return resp.get('content')

    raise Exception(resp.get('content'))

def create_user(username, email, password):
    action = 'user/create/'
    data = json.dumps(dict(username=username, email=email, password=password))
    resp, cookie = post_json(action, data)
    return check_status(resp), cookie

def login_by_username(username, password):
    action = 'user/login/'
    data = json.dumps(dict(username=username, password=password))
    resp, cookie = post_json(action, data)
    return check_status(resp, lambda x: WordfeudSession(cookie, x))


class WordfeudError(Exception):
    def __init__(self, error):
        self.message = error.get('message', '')
        self.type = error.get('type')


class WordfeudSession:
    def __init__(self, cookie, userdata):
        self.cookie = cookie
        self.userdata = userdata
        self.id = self.userdata.get('id')
        self.username = userdata.get('username')
        self.cookies = userdata.get('cookies', False)
        self.email = userdata.get('email')
        self.banner = userdata.get('banner')
        self.pontiflex_weight = userdata.get('pontiflex_weight')

    def get_status(self):
        action = 'user/status/'
        resp = self._post_json(action)
        return check_status(resp, lambda s: Status(self, s))

    def _post_json(self, action, json_data=''):
        resp, cookie = post_json(action, json_data, self.cookie)

        if resp.get('status', 'success') == 'error':
            error = resp.get('content')

            if error.get('type') == 'login_required':
                session = login_by_username(config.username, config.password) 
                self.__init__(session.cookie, session.userdata)
                resp, cookie = post_json(action, json_data, self.cookie)
            else:
                log.warn("Error communicating with Wordfeud: %s" % error)
                raise WordfeudError(error)

        self.cookie = cookie
        return resp

    def list_games(self):
        action = 'user/games/'
        resp = self._post_json(action)
        games = check_status(resp).get('games')
        return map(lambda x: Game(self, dict(game=x)), games)

    def accept_invitation(self, invite_id):
        action = 'invite/%d/accept/' % invite_id
        resp = self._post_json(action)
        return True

    def reject_invitation(self, invite_id):
        action = 'invite/%d/reject/' % invite_id
        resp = self._post_json(action)
        return True


class Status:
    def __init__(self, session, statusdata):
        self.statusdata = statusdata
        self.games = map(lambda x: GameStatus(session, x), statusdata.get('games', []))
        self.invites_sent = statusdata.get('invites_sent', [])
        self.invites_received = statusdata.get('invites_received', [])


class Move:
    def __init__(self, movedata):
        self.movedata = movedata

        if movedata is not None:
            self.move_type = movedata.get('move_type')
            self.user_id = movedata.get('user_id')


class Player:
    def __init__(self, playerdata):
        self.data = playerdata
        self.username = playerdata.get('username')
        self.position = playerdata.get('position')
        self.score = playerdata.get('score')
        self.id = playerdata.get('id')
        self.rack = playerdata.get('rack', [])


class Word:
    ACROSS = 1
    DOWN = 2

    def __init__(self, word, x, y, direction):
        self.word = word
        self.x0 = x
        self.y0 = y
        self.direction = direction

    def get_move(self, board):
        move = []

        if self.direction == Word.ACROSS:
            for x in range(self.x0, self.x0 + len(self.word)):
                letter = self.word[x - self.x0]
                board_letter = board.get((x, self.y0), None)

                if board_letter is not None:
                    if board_letter != letter.upper():
                        raise Exception('Invalid move')
                else:
                    blank = letter == letter.upper()
                    move.append([x, self.y0, letter.upper(), blank])
        elif self.direction == Word.DOWN:
            for y in range(self.y0, self.y0 + len(self.word)):
                letter = self.word[y - self.y0]
                board_letter = board.get((self.x0, y), None)

                if board_letter is not None:
                    if board_letter != letter.upper():
                        raise Exception('Invalid move')
                else:
                    blank = letter == letter.upper()
                    move.append([self.x0, y, letter.upper(), blank])
        else:
            raise Exception('Invalid direction: ' + direction)

        return move


class GameStatus(object):
    def __init__(self, session, gamedata):
        self.session = session
        self.gamedata = gamedata
        self.id = gamedata.get('id')
        self.updated = datetime.fromtimestamp(gamedata.get('updated'))
        self.chat_count = gamedata.get('chat_count')

    def get_game(self):
        action = 'game/%d/' % self.id
        resp = self.session._post_json(action)
        return check_status(resp, lambda x: Game(self.session, x))


class Game(GameStatus):
    def __init__(self, session, gamedata):
        self.gamedata = gamedata
        self.game = gamedata.get('game')

        super(Game, self).__init__(session, self.game)

        # self.id = self.game.get('id')
        # self.updated = datetime.fromtimestamp(self.game.get('updated'))
        # self.chat_count = self.game.get('chat_count')
        self.current_player = self.game.get('current_player')
        self.created = datetime.fromtimestamp(self.game.get('created'))
        self.move_count = self.game.get('move_count')
        self.tiles = self.game.get('tiles')
        self.is_running = self.game.get('is_running')
        self.last_move = self.game.get('last_move')
        self.players = self.game.get('players')
        self.end_game = self.game.get('end_game')
        self.board = self.game.get('board')
        self.bag_count = self.game.get('bag_count')
        self.pass_count = self.game.get('pass_count')
        self.ruleset = self.game.get('ruleset')

        self.board_type = 'normal' if self.board == 1 else 'random'

        self.me = None
        self.opponents = []

        for player in self.players:
            player = Player(player)

            if player.id == session.id:
                self.me = player
            else:
                self.opponents.append(player)

    def get_tile_points(self):
        '''Returns the points awarded for individual tiles/letters.'''
        action = 'tile_points/%s/' % self.ruleset
        resp = self.session._post_json(action)
        return check_status(resp, lambda x: x.get('tile_points'))

    def get_board_squares(self):
        '''Returns the premium tiles of the board.'''
        action = 'board/%s/' % self.board

        if appengine:
            board = memcache.get(action)

            if board:
                log.debug('Board %d found in cache' % self.board)
                return board

        log.debug('Fetch board %d from Wordfeud' % self.board)
        resp = self.session._post_json(action)
        board = check_status(resp, lambda x: x.get('board'))

        if appengine:
            memcache.set(action, board)

        return board

    def is_my_turn(self):
        return self.me.position == self.current_player

    def get_board(self):
        return Board(self.tiles)

    def play(self, word, x0, y0, direction):
        board = self.get_board()
        w = Word(word, x0, y0, direction)
        move = w.get_move(board)
        log.debug('Have: %s', self.me.rack)
        log.debug('Want to play: %s', move)
        action = 'game/%d/move/' % self.id
        json_data = json.dumps(dict(ruleset=self.ruleset,
                                    words=[word.upper()],
                                    move=move))
        resp = self.session._post_json(action, json_data)
        update = check_status(resp)

        # Update rack
        new_rack = list(self.me.rack)
    
        for letter in map(lambda x: '' if x[3] else x[2], move):
            new_rack.remove(letter)

        for letter in update.get('new_tiles', []):
            new_rack.append(letter)

        new_me = dict(self.me.data)
        new_me.update(score=self.me.score + update.get('points', 0),
                     rack=new_rack)
        new_game = dict(self.game)
        new_game.update(updated=update.get('updated'),
                        players=[new_me] + map(lambda p: p.data, self.opponents))
        return Game(self.session, dict(game=new_game))

    def pass_(self):
        action = 'game/%d/pass/' % self.id
        resp = self.session._post_json(action)
        return check_status(resp)

    def resign(self):
        action = 'game/%d/resign/' % self.id
        resp = self.session._post_json(action)
        return check_status(resp)


class Swedish:
    count = dict()
    count['A'] = 1	
    count['B'] = 4	
    count['C'] = 1
    count['D'] = 1	
    count['E'] = 1	
    count['F'] = 3	
    count['G'] = 2	
    count['H'] = 2	
    count['I'] = 1	
    count['J'] = 7	
    count['K'] = 2	
    count['L'] = 1	
    count['M'] = 2	
    count['N'] = 1	
    count['O'] = 2	
    count['P'] = 4	
    count['R'] = 1	
    count['S'] = 1	
    count['T'] = 1	
    count['U'] = 4	
    count['V'] = 3	
    count['X'] = 8	
    count['Y'] = 7	
    count['Z'] = 8	
    count['Ä'] = 3	
    count['Å'] = 4
    count['Ö'] = 4	
    count['_'] = 2

    value = dict()
    value['A'] = 8
    value['B'] = 2
    value['C'] = 10
    value['D'] = 5
    value['E'] = 7
    value['F'] = 2
    value['G'] = 3
    value['H'] = 2
    value['I'] = 5
    value['J'] = 1
    value['K'] = 3
    value['L'] = 5
    value['M'] = 3
    value['N'] = 6
    value['O'] = 5
    value['P'] = 2
    value['R'] = 8
    value['S'] = 8
    value['T'] = 8
    value['U'] = 3
    value['V'] = 2
    value['X'] = 1
    value['Y'] = 1
    value['Z'] = 1
    value[u'Ä'] = 2
    value[u'Å'] = 2
    value[u'Ö'] = 2


def score_word(word):
    return sum(map(Swedish.value.get, word))


class Board(UserDict):
    def __init__(self, tiles=[]):
        self.premium = dict()
        self.premium[(0, 0)] = '3L'
        self.premium[(4, 0)] = '3W'
        self.premium[(7, 0)] = '2L'
        self.premium[(10, 0)] = '3W'
        self.premium[(14, 0)] = '3L'
        self.premium[(1, 1)] = '2L'
        self.premium[(5, 1)] = '3L'
        self.premium[(9, 1)] = '3L'
        self.premium[(13, 1)] = '2L'

        board = dict()

        for tile in tiles:
            x, y, letter, blank = tile
            board[(x, y)] = letter

        UserDict.__init__(self, board)

    def transpose(self):
        return TransposedBoard(self)

    def __repr__(self):
        lines = [('+---' * 15) + '+']

        for y in range(0, 15):
            lines.append('|' + '|'.join(map(lambda x: self.get((x, y), '').encode('latin-1').center(3), range(0, 15))) + '|')
            lines.append(('+---' * 15) + '+')

        return '\n'.join(lines)

class TransposedBoard(Board):
    def __init__(self, board):
        Board.__init__(self)
        self.board = board

    def get(self, key, default=None):
        y, x = key
        return self.board.get((x, y), default)

    def __getitem__(self, key):
        y, x = key
        return board[(x, y)]


class Tile:
    DOUBLE_WORD = 3
    DOUBLE_LETTER = 1
    TRIPLE_WORD = 5
    TRIPLE_LETTER = 4

    def __init__(self):
        self.cross = [0,0]
        self.side = [0,0]
        self.special = 0 
        self.letter = ' '
        self.anchor = False
        self.score = 0

    def __repr__(self):
        if self.letter == ' ':
            if self.special == DOUBLE_WORD:
                return '2W'

        if self.special == DOUBLE_LETTER:
            return '2L'

        if self.special == TRIPLE_WORD:
            return '2W'

        if self.special == TRIPLE_LETTER:
            return '2L'

        return self.letter
    
