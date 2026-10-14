# Host tests for the stimulator wrapper. No Arduino toolchain needed.
CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Werror -O0 -g -I.

test: test_neurostimduino
	./test_neurostimduino

test_neurostimduino: test_neurostimduino.cpp Arduino.h Wire.h ../../stimulation_control/neurostimduino.h
	$(CXX) $(CXXFLAGS) -o $@ test_neurostimduino.cpp

clean:
	rm -f test_neurostimduino

.PHONY: test clean
