from agent import config
from agent.app import app


def main() -> None:
    app.run(host="0.0.0.0", port=config.PORT)


if __name__ == "__main__":
    main()
