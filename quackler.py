# -*- encoding: utf-8 -*-
from datetime import datetime
from string import ascii_uppercase
from wordfeud import *
import codecs
import logging
import re
import subprocess
import time

logging.basicConfig(level=logging.INFO)


def swapcase(v):
    if v == 'å':
        return u'Å'
    if v == 'Å':
        return u'å'
    if v == 'ä':
        return u'Ä'
    if v == 'Ä':
        return u'ä'
    if v == 'ö':
        return u'Ö'
    if v == 'Ö':
        return u'ö'

    return v.swapcase()


def gcg_write_header(game):
    with codecs.open('games/%s.gcg' % game.id, 'w+', 'utf-8') as f:
        players = map(Player, game.players)

        for player in players:
            print >>f, '#player%d %s %s' % (player.position + 1, player.username, player.username)

        print >>f, '#title Game %d' % game.id

        for player in players:
            print >>f, '#rack%d %s' % (player.position + 1, 
                                       '' if player.rack is None else ''.join(player.rack))

        print >>f, '#id Wordfeud %d' % game.id


def gcg_write_last_move(game):
    move = game.last_move
    move_type = move.get('move_type')

    with codecs.open('games/%d.gcg' % game.id, 'a', 'utf-8') as f:
        user_id = move.get('user_id')
        player = Player(filter(lambda x: x.get('id') == user_id, game.players)[0]) 

        if move_type == 'pass':
            print >>f, '>%s: %s - +0 %d' % (player.username,
                                           ''.join(map(lambda x: x if x else '?', player.rack)),
                                           player.score)
        elif move_type == 'move':
            logging.info(move)
            main_word = move.get('main_word')
            tiles = move.get('move')
            tile0 = tiles[0]
            letters = map(lambda x: x[2].lower() if x[3] else x[2], tiles)
            rack = ''.join(map(lambda x: '?' if x[3] else x[2], tiles))
            word = ''.join(letters)

            if all(map(lambda x: x[0] == tile0[0], tiles)):  # down
                if all(map(lambda x: x[1] >= tile0[1], tiles)):  # "forward"
                    tile0 = [tile0[0], tile0[1] - len(main_word) + len(tiles)]
                else:
                    pass

                place = '%s%d' % (ascii_uppercase[tile0[0]], tile0[1] + 1)
            else:
                if all(map(lambda x: x[1] >= tile0[1], tiles)):  # "forward"
                    tile0 = [tile0[0], tile0[1] - len(main_word) + len(tiles)]
                else:
                    pass

                place = '%d%s' % (tile0[1] + 1, ascii_uppercase[tile0[0]])

            print >>f, '>%s: %s %s %s %d %d' % (player.username, rack, place,
                                               main_word, int(move.get('points')),
                                               player.score)


def gcg_write_incomplete(game):
    with codecs.open('games/%d.gcg' % game.id, 'a', 'utf-8') as f:
        rack = ''.join(map(lambda x: x if x else '?', game.me.rack))
        print >>f, '#incomplete %s' % rack


def handle_invitation(invitation):
    pass


class Bot(object):
    def __init__(self, strategy):
        self.strategy = strategy

    def handle_game(self, game):
        self.strategy.evaluate(game)

class QuackleStrategy(object):
    """
    Strategy
    """
    def evaluate(self, game):
        if not game.is_running:
            logging.info('Game %d is dead' % game.id)
            gcg_write_last_move(game)
            return

        if game.last_move is None:  # New game
            gcg_write_header(game)
        else:
            gcg_write_last_move(game)

        if game.is_my_turn():
            gcg_write_incomplete(game)
            self.get_move(game)
            gcg_write_last_move(game.get_game())

    def get_move(self, game):
        moves = subprocess.check_output(['./a.out', 'games/%d.gcg' % game.id]).split('\n')

        for move in moves:
            if not move:
                return

            if move.startswith('nonmove'):
                return

            logging.info("Quackle suggests: %s" % move)
            place, word, _ = move.split(None, 2)
            logging.debug(place, word)
            word = word.decode('utf-8')

            # Number first for horizontal plays
            direction = Word.ACROSS if place[0].isdigit() else Word.DOWN
            board = game.get_board()

            if direction == Word.ACROSS:
                y, x = re.findall(r'([0-9]+)([a-zA-Z]+)', place)[0]
                x = ascii_uppercase.index(x)
                y = int(y) - 1
                w = ''.join([board[(x + i, y)] if v == '.' else swapcase(v) for i, v in enumerate(word)])
            else:
                x, y = re.findall(r'([a-zA-Z]+)([0-9]+)', place)[0]
                x = ascii_uppercase.index(x)
                y = int(y) - 1
                w = ''.join([board[(x, y + i)] if v == '.' else swapcase(v) for i, v in enumerate(word)])

            try:
                logging.info('Attempting %s @ %d, %d', str(w), x, y)
                game.play(w, x, y, direction)
                return
            except WordfeudError, e:
                logging.error('Error placing %s' % word)

        logging.info('Pass')
        game.pass_()


def main():
    import config
    W = login_by_username(config.username, config.password)
    strategy = QuackleStrategy()
    last_updated = None  # datetime.now()

    while True:
        logging.info("Checking for updates")
        s = W.get_status()

        for g in s.games:
            if last_updated is None or g.updated > last_updated:
                logging.info('Game %d updated' % g.id)
                strategy.evaluate(g.get_game())

        for invitation in s.invites_received:
            if invitation.get('ruleset') in "48":
                logging.info('Accepted %s' % invitation)
                W.accept_invitation(invitation.get('id'))

        last_updated = datetime.now()
        time.sleep(30)

if __name__ == '__main__':
    main()
