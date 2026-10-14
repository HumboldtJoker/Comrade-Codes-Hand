// Host stand-in for TwoWire: records every frame written and answers reads from a script. Tests only.
#pragma once
#include <cstdint>
#include <cstddef>
#include <deque>
#include <vector>

struct Frame {
  uint8_t addr;
  std::vector<uint8_t> bytes;
};

class TwoWire {
 public:
  std::vector<Frame> frames;        // every transmission, including empty presence probes
  std::deque<int> replies;          // answers to requestFrom, in order
  int default_reply = 0;            // answer when the script is empty; -1 = the board says nothing
  uint8_t end_status = 0;           // what endTransmission returns (0 = acknowledged)
  int begun = 0;

  void begin() { begun++; }
  void beginTransmission(uint8_t a) { cur_addr_ = a; cur_.clear(); }
  size_t write(uint8_t b) { cur_.push_back(b); return 1; }
  uint8_t endTransmission(bool = true) {
    frames.push_back({cur_addr_, cur_});
    return end_status;
  }
  uint8_t requestFrom(uint8_t, uint8_t n) {
    pending_.clear();
    for (uint8_t i = 0; i < n; i++) {
      int r = replies.empty() ? default_reply : replies.front();
      if (!replies.empty()) replies.pop_front();
      if (r < 0) break;
      pending_.push_back((uint8_t)r);
    }
    return (uint8_t)pending_.size();
  }
  int available() { return (int)pending_.size(); }
  int read() {
    if (pending_.empty()) return -1;
    int b = pending_.front();
    pending_.pop_front();
    return b;
  }
  // Frames with content (presence probes are empty).
  std::vector<std::vector<uint8_t>> commands() const {
    std::vector<std::vector<uint8_t>> out;
    for (const auto& f : frames)
      if (!f.bytes.empty()) out.push_back(f.bytes);
    return out;
  }
  void clear() { frames.clear(); }

 private:
  uint8_t cur_addr_ = 0;
  std::vector<uint8_t> cur_;
  std::deque<uint8_t> pending_;
};

extern TwoWire Wire, Wire1;
