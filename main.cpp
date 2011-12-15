#include <QtCore>
#include <boardparameters.h>
#include <bogowinplayer.h>
#include <datamanager.h>
#include <game.h>
#include <lexiconparameters.h>
#include <reporter.h>
#include <sim.h>
#include <strategyparameters.h>
#include <alphabetparameters.h>
#include <move.h>
#include <quackleio/gcgio.h>
#include <quackleio/util.h>
#include <quackleio/flexiblealphabet.h>

#include "trademarkedboards.h"

int main(int argc, char **argv) {
  Quackle::DataManager dataManager;
  dataManager.setDataDirectory("data");
  dataManager.lexiconParameters()->loadDawg(Quackle::LexiconParameters::findDictionaryFile("saol13.dawg"));
  dataManager.lexiconParameters()->loadGaddag(Quackle::LexiconParameters::findDictionaryFile("saol13.gaddag"));
  dataManager.setBoardParameters(new ScrabbleBoard());

  QString alphabetFile = QuackleIO::Util::stdStringToQString(Quackle::AlphabetParameters::findAlphabetFile("swedish.quackle_alphabet"));
  QuackleIO::FlexibleAlphabetParameters *flexure = new QuackleIO::FlexibleAlphabetParameters;

  if (!flexure->load(alphabetFile)) {
    UVcerr << "Couldn't load alphabet!" << std::endl;
    delete flexure;
    return 1;
  }

  dataManager.setAlphabetParameters(flexure);

  QuackleIO::GCGIO io;
  QString path(argv[0]);
  QFile file(argv[1]);

  if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
    UVcerr << "Could not open gcg!" << std::endl;
    return 1;
  }

  QTextStream in(&file);
  Quackle::Game *game = io.read(in, QuackleIO::Logania::MaintainBoardPreparation);
  file.close();

  Quackle::GamePosition gamePos = game->currentPosition();
  Quackle::SmartBogowin p;
  gamePos.kibitzAs(&p, 5);
  UVcout << gamePos.moves() << std::endl;
  UVcout << gamePos << std::endl;
  return 0;
/*

  Quackle::PlayerList players;

  Quackle::Player p1(MARK_UV("p1"), Quackle::Player::HumanPlayerType, 1);
  p1.setRack(QUACKLE_ALPHABET_PARAMETERS->encode(MARK_UV("DNWNAEN")));
  players.push_back(p1);

  Quackle::Player p2(MARK_UV("p2"), Quackle::Player::HumanPlayerType, 2);
  players.push_back(p2);

  Quackle::Game game;
  game.setPlayers(players);
  game.addPosition();

  game.commitMove(Quackle::Move::createPlaceMove(MARK_UV("7i"), QUACKLE_ALPHABET_PARAMETERS->encode(MARK_UV("WANNED"))));

  game.currentPosition().setCurrentPlayerRack(QUACKLE_ALPHABET_PARAMETERS->encode(MARK_UV("IATHESO")));

  std::cout << "====================" << std::endl;
  UVString report;
  Quackle::StaticPlayer player;
  Quackle::Reporter::reportGame(*game, &player, &report);
  UVcout << report;
*/



  delete game;
  return 0;
}
