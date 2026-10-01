import logging
import signal
import sys

from . import config as cfgmod
from .db import DB
from .scheduler import Scheduler
from .webapp import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("autotask.daemon")


def main():
    cfg, cfg_path = cfgmod.load_config()
    cfgmod.ensure_dirs(cfg)
    log.info("config loaded from %s", cfg_path)
    log.info("scripts_dir=%s data_dir=%s", cfg["scripts_dir"], cfg["data_dir"])

    db = DB(cfg["data_dir"])
    recovered = db.recover_interrupted_runs()
    if recovered:
        log.warning("marked %d interrupted task run(s) as failed after startup", recovered)
    scheduler = Scheduler(cfg, db)
    scheduler.start()

    def handle_sigterm(signum, frame):
        log.info("received signal %s, shutting down", signum)
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    app = create_app(cfg, cfg_path, db, scheduler)
    host = cfg.get("bind_host", "::")
    port = cfg.get("port", 8990)
    log.info("web ui listening on [%s]:%s", host, port)
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
