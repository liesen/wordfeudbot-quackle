# Not really a makefile, but here it goes...
QUACKLE_DIR="../quackle"

player:
	g++ -I/usr/local/include/QtCore/ -F/usr/local/lib -I${QUACKLE_DIR} -I${QUACKLE_DIR}/test -framework QtCore -L${QUACKLE_DIR} -lquackle -L${QUACKLE_DIR}/quackleio -lquackleio main.cpp ${QUACKLE_DIR}/test/trademarkedboards.cpp -o player
