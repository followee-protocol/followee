/* Coordinator scenario-clock shim (Gate G1 and the premature-retention
 * contrast, ACCEPTANCE.md Phase 3 step 6a).
 *
 * The frozen Rust participant's `relay serve` binary reads the system
 * realtime clock; the gate scenario pins the *relay's* clock at an
 * explicit instant (the `changes-premature-retained` /
 * `resolve-premature-retained` scenario clock). This LD_PRELOAD shim
 * configures the process environment's realtime clock to that instant:
 * it intercepts clock_gettime/gettimeofday/time and reports the fixed
 * wall-clock value from FOLLOWEE_SCENARIO_NOW_MS. It changes no
 * participant code and makes no protocol decision; it is environment
 * configuration, exactly like setting the machine clock for a test.
 * Monotonic clocks are passed through untouched.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/time.h>
#include <time.h>

static int64_t scenario_now_ms(void) {
  static int64_t cached = -2;
  if (cached == -2) {
    const char *value = getenv("FOLLOWEE_SCENARIO_NOW_MS");
    cached = value ? strtoll(value, NULL, 10) : -1;
  }
  return cached;
}

typedef int (*clock_gettime_fn)(clockid_t, struct timespec *);

int clock_gettime(clockid_t clk_id, struct timespec *tp) {
  static clock_gettime_fn real = NULL;
  if (!real) {
    real = (clock_gettime_fn)dlsym(RTLD_NEXT, "clock_gettime");
  }
  int result = real(clk_id, tp);
  int64_t now_ms = scenario_now_ms();
  if (result == 0 && now_ms >= 0 &&
      (clk_id == CLOCK_REALTIME || clk_id == CLOCK_REALTIME_COARSE)) {
    tp->tv_sec = (time_t)(now_ms / 1000);
    tp->tv_nsec = (long)(now_ms % 1000) * 1000000L;
  }
  return result;
}

int gettimeofday(struct timeval *tv, void *tz) {
  (void)tz;
  struct timespec ts;
  int result = clock_gettime(CLOCK_REALTIME, &ts);
  if (result == 0 && tv) {
    tv->tv_sec = ts.tv_sec;
    tv->tv_usec = ts.tv_nsec / 1000;
  }
  return result;
}

time_t time(time_t *tloc) {
  struct timespec ts;
  if (clock_gettime(CLOCK_REALTIME, &ts) != 0) {
    return (time_t)-1;
  }
  if (tloc) {
    *tloc = ts.tv_sec;
  }
  return ts.tv_sec;
}
