// Host tests for the NeuroStimDuino safety wrapper (software/arduino/stimulation_control/neurostimduino.h).
//
//   make -C software/arduino/tests/host        build and run; exit 1 if any test fails
//
// The wrapper is compiled as if for the Due (__SAM3X8E__), so it must use Wire1. The fake Wire records every
// frame; each expected frame below is the vendor library's format: [byte count][command][channel][data...].
#define __SAM3X8E__ 1
#include "Arduino.h"
#include "Wire.h"
#include "../../stimulation_control/neurostimduino.h"

#include <cstdio>
#include <functional>
#include <string>
#include <vector>

unsigned long g_millis = 0;
FakeSerial Serial;
TwoWire Wire, Wire1;

typedef std::vector<uint8_t> Bytes;
static int g_failed = 0, g_run = 0;
static std::string g_current;

#define CHECK(cond)                                                                    \
  do {                                                                                 \
    if (!(cond)) {                                                                     \
      std::printf("FAIL %s: %s (line %d)\n", g_current.c_str(), #cond, __LINE__);    \
      throw 1;                                                                         \
    }                                                                                  \
  } while (0)

static void reset_world() {
  g_millis = 0;
  Serial = FakeSerial();
  Wire = TwoWire();
  Wire1 = TwoWire();
}

static void run(const char* name, const std::function<void()>& fn) {
  reset_world();
  g_current = name;
  g_run++;
  try {
    fn();
    std::printf("ok   %s\n", name);
  } catch (...) {
    g_failed++;
  }
}

static Bytes at(const std::vector<Bytes>& v, size_t i) {
  CHECK(i < v.size());
  return v[i];
}

static bool has(const std::vector<Bytes>& cmds, const Bytes& want) {
  for (const auto& c : cmds)
    if (c == want) return true;
  return false;
}
static int count_cmd(const std::vector<Bytes>& cmds, uint8_t cmd) {
  int n = 0;
  for (const auto& c : cmds)
    if (c.size() >= 2 && c[1] == cmd) n++;
  return n;
}
static const StimParams OK_PARAMS = {3000, 200, 30, 200, 0, true};

static NeuroStimDuino ready() {          // begun, enabled, frames cleared
  NeuroStimDuino s;
  CHECK(s.begin());
  s.setOutputEnabled(true);
  Wire1.clear();
  return s;
}

int main() {
  std::setvbuf(stdout, nullptr, _IONBF, 0);                    // a crash must not swallow the FAIL lines
  run("begin_uses_wire1_stops_both_channels_disables_and_turns_ramping_on", [] {
    NeuroStimDuino s;
    CHECK(s.begin());
    auto c = Wire1.commands();
    CHECK(has(c, Bytes{2, NSD_CMD_STOP, 1}) && has(c, Bytes{2, NSD_CMD_STOP, 2}));
    CHECK(has(c, Bytes{3, NSD_CMD_ENAB, 1, 0}) && has(c, Bytes{3, NSD_CMD_ENAB, 2, 0}));
    CHECK(has(c, Bytes{3, NSD_CMD_RAMP, 0xFF, 1}));
    CHECK(Wire.frames.empty() && Wire.begun == 0 && Wire1.begun == 1);
    for (const auto& f : Wire1.frames) CHECK(f.addr == 0x1A);
  });

  run("begin_fails_when_no_board_answers", [] {
    Wire1.end_status = 2;
    NeuroStimDuino s;
    CHECK(!s.begin());
  });

  run("set_params_sends_ampl_freq_durn_on_wire_channel_1_for_api_channel_0", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(StimParams{3000, 300, 30, 200, 0, true}));
    auto c = Wire1.commands();
    CHECK(c.size() == 3);
    CHECK(at(c, 0) == (Bytes{3, NSD_CMD_AMPL, 1, 12}));           // 3000 uA / 240 = 12.5 -> 12 steps
    CHECK(at(c, 1) == (Bytes{3, NSD_CMD_FREQ, 1, 30}));
    CHECK(at(c, 2) == (Bytes{4, NSD_CMD_DURN, 1, 300 & 0xFF, 300 >> 8}));
  });

  run("api_channel_1_is_wire_channel_2", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(StimParams{2400, 200, 30, 200, 1, true}));
    CHECK(at(Wire1.commands(), 0) == (Bytes{3, NSD_CMD_AMPL, 2, 10}));
  });

  run("current_is_rounded_down_to_the_boards_steps_never_up", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(StimParams{MAX_CURRENT_UA, 200, 30, 200, 0, true}));
    CHECK(at(Wire1.commands(), 0)[3] == MAX_CURRENT_UA / 240);
    CHECK((int)at(Wire1.commands(), 0)[3] * 240 <= MAX_CURRENT_UA);
    Wire1.clear();
    CHECK(s.setParams(StimParams{239, 200, 30, 200, 0, true}));
    CHECK(at(Wire1.commands(), 0)[3] == 0);
  });

  run("above_the_working_limit_is_refused_and_nothing_reaches_the_board", [] {
    NeuroStimDuino s = ready();
    CHECK(!s.setParams(StimParams{MAX_CURRENT_UA + 1, 200, 30, 200, 0, true}));
    CHECK(Wire1.commands().empty());
    CHECK(!s.isLatched());
  });

  run("above_the_absolute_limit_is_an_emergency_stop", [] {
    NeuroStimDuino s = ready();
    CHECK(!s.setParams(StimParams{ABSOLUTE_MAX_UA + 1, 200, 30, 200, 0, true}));
    auto c = Wire1.commands();
    CHECK(!c.empty() && at(c, 0) == (Bytes{1, NSD_CMD_EOFF}));
    CHECK(s.isLatched());
    CHECK(count_cmd(c, NSD_CMD_AMPL) == 0);
  });

  run("a_negative_current_beyond_the_absolute_limit_is_an_emergency_stop_too", [] {
    NeuroStimDuino s = ready();
    CHECK(!s.setParams(StimParams{-(ABSOLUTE_MAX_UA + 1), 200, 30, 200, 0, true}));
    CHECK(s.isLatched());
  });

  run("a_small_negative_current_is_refused_without_a_stop", [] {
    NeuroStimDuino s = ready();
    CHECK(!s.setParams(StimParams{-240, 200, 30, 200, 0, true}));
    CHECK(Wire1.commands().empty() && !s.isLatched());
  });

  run("every_other_bad_field_is_refused_with_nothing_sent", [] {
    NeuroStimDuino s = ready();
    StimParams bad[] = {
        {3000, MAX_PULSE_WIDTH_US + 1, 30, 200, 0, true}, {3000, MIN_PULSE_WIDTH_US - 1, 30, 200, 0, true},
        {3000, 200, MIN_FREQUENCY_HZ - 1, 200, 0, true},  {3000, 200, MAX_FREQUENCY_HZ + 1, 200, 0, true},
        {3000, 200, 30, 0, 0, true},                      {3000, 200, 30, MAX_STIM_DURATION_MS + 1, 0, true},
        {3000, 200, 30, 200, 0, false},                   {3000, 200, 30, 200, 2, true},
    };
    for (const auto& p : bad) {
      CHECK(!s.setParams(p));
    }
    CHECK(Wire1.commands().empty() && !s.isLatched());
  });

  run("the_limits_themselves_are_accepted", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(StimParams{MAX_CURRENT_UA, MAX_PULSE_WIDTH_US, MAX_FREQUENCY_HZ, MAX_STIM_DURATION_MS, 1, true}));
    CHECK(s.setParams(StimParams{0, MIN_PULSE_WIDTH_US, MIN_FREQUENCY_HZ, 1, 0, true}));
  });

  run("a_refused_set_after_an_accepted_one_leaves_nothing_to_start", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS));
    CHECK(!s.setParams(StimParams{MAX_CURRENT_UA + 1, 200, 30, 200, 0, true}));
    Wire1.clear();
    CHECK(!s.startStim());
    CHECK(count_cmd(Wire1.commands(), NSD_CMD_STIM) == 0);
  });

  run("start_needs_enabled_output_and_accepted_parameters", [] {
    NeuroStimDuino s;
    CHECK(s.begin());
    CHECK(s.setParams(OK_PARAMS));
    CHECK(!s.startStim());                                     // not enabled
    NeuroStimDuino t = ready();
    CHECK(!t.startStim());                                     // enabled, never given parameters
    CHECK(count_cmd(Wire1.commands(), NSD_CMD_STIM) == 0);
  });

  run("stim_carries_a_lease_of_whole_seconds_and_never_the_continuous_flag", [] {
    const uint16_t durations[] = {1, 200, 1000, 1001, 2500, MAX_STIM_DURATION_MS};
    const uint8_t leases[] = {1, 1, 1, 2, 3, 5};
    for (int i = 0; i < 6; i++) {
      reset_world();
      NeuroStimDuino s = ready();
      StimParams p = OK_PARAMS;
      p.duration_ms = durations[i];
      p.channel = 1;
      CHECK(s.setParams(p));
      Wire1.clear();
      CHECK(s.startStim());
      auto c = Wire1.commands();
      CHECK(c.size() == 1 && at(c, 0) == (Bytes{4, NSD_CMD_STIM, 2, leases[i], 0}));
    }
  });

  run("the_emergency_stop_sends_eoff_first_then_stops_both_channels_and_latches", [] {
    NeuroStimDuino s = ready();
    s.emergencyStop();
    auto c = Wire1.commands();
    CHECK(c.size() >= 3);
    CHECK(at(c, 0) == (Bytes{1, NSD_CMD_EOFF}));
    CHECK(at(c, 1) == (Bytes{2, NSD_CMD_STOP, 1}) && at(c, 2) == (Bytes{2, NSD_CMD_STOP, 2}));
    CHECK(s.isLatched() && !s.isOutputEnabled());
  });

  run("nothing_starts_while_latched", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS));
    s.emergencyStop();
    Wire1.clear();
    s.setOutputEnabled(true);
    CHECK(!s.isOutputEnabled());
    CHECK(!s.setParams(OK_PARAMS));
    CHECK(!s.startStim());
    auto c = Wire1.commands();
    CHECK(count_cmd(c, NSD_CMD_STIM) == 0 && count_cmd(c, NSD_CMD_AMPL) == 0);
    CHECK(!has(c, Bytes{3, NSD_CMD_ENAB, 1, 1}));
  });

  run("after_a_deliberate_reset_parameters_must_be_given_again", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS));
    s.emergencyStop();
    s.resetAfterStop();
    CHECK(!s.isLatched());
    s.setOutputEnabled(true);
    CHECK(s.isOutputEnabled());
    CHECK(!s.startStim());                                     // the old parameters do not come back
    CHECK(s.setParams(OK_PARAMS) && s.startStim());
  });

  run("a_stop_the_board_does_not_confirm_is_an_emergency_stop", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS) && s.startStim());
    Wire1.clear();
    Wire1.default_reply = 255;                                 // the vendor's "has not stopped"
    s.stopStim();
    CHECK(s.isLatched());
    CHECK(has(Wire1.commands(), Bytes{1, NSD_CMD_EOFF}));
  });

  run("a_stop_with_no_answer_at_all_is_an_emergency_stop", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS) && s.startStim());
    Wire1.default_reply = -1;
    s.stopStim();
    CHECK(s.isLatched());
  });

  run("a_stop_whose_write_is_not_acknowledged_is_an_emergency_stop", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS) && s.startStim());
    Wire1.end_status = 3;
    s.stopStim();
    CHECK(s.isLatched());
  });

  run("a_confirmed_stop_does_not_latch", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS) && s.startStim());
    Wire1.clear();
    s.stopStim();
    CHECK(!s.isLatched() && !s.isStimulating());
    CHECK(Wire1.commands() == (std::vector<Bytes>{Bytes{2, NSD_CMD_STOP, 1}}));
  });

  run("stimulation_stops_at_the_end_of_its_duration", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS) && s.startStim());
    g_millis += OK_PARAMS.duration_ms - 1;
    CHECK(s.isStimulating());
    g_millis += 1;
    Wire1.clear();
    CHECK(!s.isStimulating());
    CHECK(has(Wire1.commands(), Bytes{2, NSD_CMD_STOP, 1}));
  });

  run("stimulation_left_running_past_the_maximum_is_an_emergency_stop", [] {
    NeuroStimDuino s = ready();
    StimParams p = OK_PARAMS;
    p.duration_ms = MAX_STIM_DURATION_MS;
    CHECK(s.setParams(p) && s.startStim());
    g_millis += MAX_STIM_DURATION_MS + 1;                      // the loop never called isStimulating()
    CHECK(!s.isSafetyOK());
    CHECK(s.isLatched());
  });

  run("safety_is_not_ok_while_latched_or_disconnected", [] {
    NeuroStimDuino s = ready();
    CHECK(s.isSafetyOK());
    s.emergencyStop();
    CHECK(!s.isSafetyOK());
    s.resetAfterStop();
    Wire1.end_status = 2;
    CHECK(!s.isSafetyOK());
  });

  run("disabling_the_output_stops_a_running_stimulation_and_disables_both_channels", [] {
    NeuroStimDuino s = ready();
    CHECK(s.setParams(OK_PARAMS) && s.startStim());
    Wire1.clear();
    s.setOutputEnabled(false);
    auto c = Wire1.commands();
    CHECK(has(c, Bytes{2, NSD_CMD_STOP, 1}));
    CHECK(has(c, Bytes{3, NSD_CMD_ENAB, 1, 0}) && has(c, Bytes{3, NSD_CMD_ENAB, 2, 0}));
    CHECK(!s.isStimulating());
  });

  run("a_pulse_pattern_stops_after_each_pulse_and_halts_when_a_stop_fails", [] {
    NeuroStimDuino s = ready();
    s.pulsePattern(OK_PARAMS, 3, 50);
    auto c = Wire1.commands();
    CHECK(count_cmd(c, NSD_CMD_STIM) == 3 && count_cmd(c, NSD_CMD_STOP) == 3);
    reset_world();
    NeuroStimDuino t = ready();
    Wire1.default_reply = 255;
    t.pulsePattern(OK_PARAMS, 3, 50);
    CHECK(t.isLatched());
    CHECK(count_cmd(Wire1.commands(), NSD_CMD_STIM) == 1);
  });

  run("a_refused_pattern_sends_no_stim", [] {
    NeuroStimDuino s = ready();
    StimParams p = OK_PARAMS;
    p.current_ua = MAX_CURRENT_UA + 240;
    s.pulsePattern(p, 2, 50);
    CHECK(count_cmd(Wire1.commands(), NSD_CMD_STIM) == 0);
  });

  run("calibration_returns_the_current_at_yes", [] {
    NeuroStimDuino s = ready();
    Serial.input.push_back('y');                               // answered after the first step
    CHECK(s.calibrateThreshold(0) == NSD_UA_PER_STEP);
    CHECK(count_cmd(Wire1.commands(), NSD_CMD_STIM) == 1);
  });

  run("calibration_never_passes_the_working_limit_and_any_other_key_stops_it", [] {
    NeuroStimDuino s = ready();
    CHECK(s.calibrateThreshold(0) == -1);                      // nobody answers: climbs to the limit and gives up
    for (const auto& c : Wire1.commands())
      if (c.size() == 4 && c[1] == NSD_CMD_AMPL) CHECK((int)c[3] * 240 <= MAX_CURRENT_UA);
    CHECK(count_cmd(Wire1.commands(), NSD_CMD_STIM) == MAX_CURRENT_UA / NSD_UA_PER_STEP);
    reset_world();
    NeuroStimDuino t = ready();
    Serial.input.push_back('q');
    CHECK(t.calibrateThreshold(0) == -1);
    CHECK(count_cmd(Wire1.commands(), NSD_CMD_STIM) == 1);
  });

  run("calibration_stops_when_a_stop_fails", [] {
    NeuroStimDuino s = ready();
    Wire1.default_reply = 255;
    CHECK(s.calibrateThreshold(0) == -1);
    CHECK(s.isLatched() && count_cmd(Wire1.commands(), NSD_CMD_STIM) == 1);
  });

  run("every_write_waits_for_the_board_to_process_it", [] {
    NeuroStimDuino s = ready();
    unsigned long before = g_millis;
    CHECK(s.setParams(OK_PARAMS));
    CHECK(g_millis - before >= 3 * NSD_WRITE_SETTLE_MS);
  });

  std::printf("\n%d of %d tests passed\n", g_run - g_failed, g_run);
  return g_failed ? 1 : 0;
}
