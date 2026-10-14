// Host stand-in for the parts of the Arduino core the stimulator wrapper uses. Tests only.
#pragma once
#include <cstdint>
#include <cstddef>
#include <deque>
#include <string>

extern unsigned long g_millis;
inline unsigned long millis() { return g_millis; }
inline void delay(unsigned long ms) { g_millis += ms; }

struct FakeSerial {
  std::deque<char> input;
  std::string output;
  void println(const char* s) { output += s; output += "\n"; }
  void print(const char* s) { output += s; }
  int available() { return (int)input.size(); }
  int read() {
    if (input.empty()) return -1;
    char c = input.front();
    input.pop_front();
    return c;
  }
};
extern FakeSerial Serial;
