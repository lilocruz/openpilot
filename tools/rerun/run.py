#!/usr/bin/env python3
import subprocess
import sys
import argparse
import multiprocessing
from functools import partial

from openpilot.tools.lib.logreader import LogReader
from cereal.services import SERVICE_LIST


NUM_CPUS = multiprocessing.cpu_count()
DEMO_ROUTE = "a2a0ccea32023010|2023-07-27--13-01-19"
WHEEL_URL = "https://build.rerun.io/commit/660463d/wheels"


def install():
  # currently requires a preview release build
  subprocess.run([sys.executable, "-m", "pip", "install", "--pre", "-f", WHEEL_URL, "--upgrade", "rerun-sdk"], check=True)
  print("Rerun installed")


def log_msg(msg, parent_key=''):
  stack = [(msg, parent_key)]
  while stack:
    current_msg, current_parent_key = stack.pop()
    if isinstance(current_msg, list):
      for index, item in enumerate(current_msg):
        new_key = f"{current_parent_key}/{index}"
        if isinstance(item, (int, float)):
          rr.log(str(new_key), rr.Scalar(item))
        elif isinstance(item, dict):
          stack.append((item, new_key))
    elif isinstance(current_msg, dict):
      for key, value in current_msg.items():
        new_key = f"{current_parent_key}/{key}"
        if isinstance(value, (int, float)):
          rr.log(str(new_key), rr.Scalar(value))
        elif isinstance(value, dict):
          stack.append((value, new_key))
        elif isinstance(value, list):
          for index, item in enumerate(value):
            if isinstance(item, (int, float)):
              rr.log(f"{new_key}/{index}", rr.Scalar(item))
    else:
      pass  # Not a plottable value


def createBlueprint():
  timeSeriesViews = []
  for topic in sorted(SERVICE_LIST.keys()):
    timeSeriesViews.append(rrb.TimeSeriesView(name=topic, origin=f"/{topic}/", visible=False))
    rr.log(topic, rr.SeriesLine(name=topic), timeless=True)
    blueprint = rrb.Blueprint(rrb.Grid(rrb.Vertical(*timeSeriesViews,rrb.SelectionPanel(expanded=False),rrb.TimePanel(expanded=False)),
                                        rrb.Spatial2DView(name="thumbnail", origin="/thumbnail")))
  return blueprint


def log_thumbnail(thumbnailMsg):
  bytesImgData = thumbnailMsg.get('thumbnail')
  rr.log("/thumbnail", rr.ImageEncoded(contents=bytesImgData))


def process(blueprint, lr):
  ret = []
  rr.init("rerun_test", spawn=True, default_blueprint=blueprint)
  for msg in lr:
    ret.append(msg)
    rr.set_time_nanos("TIMELINE", msg.logMonoTime)
    if msg.which() != "thumbnail":
      log_msg(msg.to_dict()[msg.which()], msg.which())
    else:
      log_thumbnail(msg.to_dict()[msg.which()])
  return ret


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="A helper to run rerun on openpilot routes",
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--demo", action="store_true", help="Use the demo route instead of providing one")
  parser.add_argument("--install", action="store_true", help="Install or update rerun")
  parser.add_argument("route_or_segment_name", nargs='?', help="The route or segment name to plot")

  if len(sys.argv) == 1:
    parser.print_help()
    sys.exit()

  args = parser.parse_args()
  if args.install:
    install()
    sys.exit()

  try:
    import rerun as rr
    import rerun.blueprint as rrb
  except ImportError:
    print("Rerun is not installed, run with --install first")
    sys.exit()

  route_or_segment_name = DEMO_ROUTE if args.demo else args.route_or_segment_name.strip()
  blueprint = createBlueprint()
  print("Getting route log paths")
  lr = LogReader(route_or_segment_name)
  lr.run_across_segments(NUM_CPUS, partial(process, blueprint))
