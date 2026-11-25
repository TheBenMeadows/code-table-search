CC ?= cc
CFLAGS ?= -O3 -Wall -Wextra
PYTHON ?= python3

osg: src/osg.c
	$(CC) $(CFLAGS) -o $@ src/osg.c

# Two classical codes as controls: the binary Hamming code (A2(7,3) = 16, cyclic group of order 7) and the
# ternary Golay code (A3(11,5) = 729, cyclic shifts and negation, order 22). Each search must finish and
# return the known size, and the verifier must accept the returned code.
check: osg
	./osg 2x7 3 control/A2-7-3/group.txt 16 60 130000 control-A2-7-3.code | tee control-A2-7-3.line
	grep -q 'COMPLETE best=16$$' control-A2-7-3.line
	$(PYTHON) src/verifyx.py 2x7 3 control-A2-7-3.code
	./osg 3x11 5 control/A3-11-5/group.txt 729 60 130000 control-A3-11-5.code | tee control-A3-11-5.line
	grep -q 'COMPLETE best=729$$' control-A3-11-5.line
	$(PYTHON) src/verifyx.py 3x11 5 control-A3-11-5.code

clean:
	rm -f osg control-*.code control-*.line

.PHONY: check clean
