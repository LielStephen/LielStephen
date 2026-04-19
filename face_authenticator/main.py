"""
main.py — Command-line interface for the Face Authenticator.

Usage examples
--------------
  python main.py register --user alice --image /path/to/alice.jpg
  python main.py authenticate --image /path/to/unknown.jpg
  python main.py list
  python main.py delete --user alice
"""

import argparse
import sys
import logging

from face_auth import FaceAuthenticator

logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.WARNING)


def cmd_register(auth: FaceAuthenticator, args: argparse.Namespace) -> int:
    result = auth.register(args.user, args.image)
    if result["success"]:
        print(f"✅  {result['message']}")
        print(f"    Total encodings stored: {result['face_count']}")
        return 0
    print(f"❌  {result['message']}")
    return 1


def cmd_authenticate(auth: FaceAuthenticator, args: argparse.Namespace) -> int:
    result = auth.authenticate(args.image)
    if result["authenticated"]:
        print(f"✅  Authenticated as '{result['username']}' (confidence: {result['confidence']:.2%})")
        return 0
    print(f"🚫  {result['message']}")
    return 1


def cmd_list(auth: FaceAuthenticator, _args: argparse.Namespace) -> int:
    users = auth.list_users()
    if not users:
        print("No users registered yet.")
    else:
        print(f"Registered users ({len(users)}):")
        for u in users:
            print(f"  • {u}")
    return 0


def cmd_delete(auth: FaceAuthenticator, args: argparse.Namespace) -> int:
    if auth.delete_user(args.user):
        print(f"🗑️   User '{args.user}' removed.")
        return 0
    print(f"⚠️   User '{args.user}' not found.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="face_authenticator",
        description="Biometric face authenticator powered by face_recognition.",
    )
    parser.add_argument(
        "--db",
        default=None,
        metavar="DIR",
        help="Path to the face database directory (default: known_faces/)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.50,
        metavar="T",
        help="Match tolerance 0–1; lower is stricter (default: 0.50)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # register
    p_reg = sub.add_parser("register", help="Register a new user face.")
    p_reg.add_argument("--user", "-u", required=True, help="Username to register.")
    p_reg.add_argument("--image", "-i", required=True, help="Path to the face image.")

    # authenticate
    p_auth = sub.add_parser("authenticate", aliases=["auth"], help="Authenticate a face.")
    p_auth.add_argument("--image", "-i", required=True, help="Path to the face image to check.")

    # list
    sub.add_parser("list", help="List all registered users.")

    # delete
    p_del = sub.add_parser("delete", help="Delete a registered user.")
    p_del.add_argument("--user", "-u", required=True, help="Username to delete.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    kwargs: dict = {"tolerance": args.tolerance}
    if args.db:
        kwargs["db_dir"] = args.db
    auth = FaceAuthenticator(**kwargs)

    handlers = {
        "register": cmd_register,
        "authenticate": cmd_authenticate,
        "auth": cmd_authenticate,
        "list": cmd_list,
        "delete": cmd_delete,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(auth, args))


if __name__ == "__main__":
    main()
