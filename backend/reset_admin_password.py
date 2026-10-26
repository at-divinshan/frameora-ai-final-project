"""Manual, single-account Admin password reset. Never runs on import.

Run with the existing backend virtual environment in an interactive terminal.
No passwords or hashes are written to files, arguments, logs, or output.
"""

import getpass
import sys
import warnings
from typing import Annotated


ADMIN_NAME = "Frameora Admin"
ADMIN_EMAIL = "admin@frameora.com"


class ResetAborted(Exception):
    """An expected refusal with a safe, non-sensitive message."""


def main() -> int:
    # Avoid creating Python bytecode files when importing the application.
    sys.dont_write_bytecode = True
    engine = None
    commit_attempted = False
    password = confirmation = None

    try:
        if not sys.stdin.isatty():
            raise ResetAborted("Run this script directly in an interactive local terminal.")

        from pydantic import TypeAdapter, ValidationError
        from sqlalchemy import select, update

        from app.core.security import hash_password
        from app.database.connection import engine
        from app.models.user import User
        from app.schemas.auth import RegisterRequest

        print(f"Reset password for {ADMIN_NAME} ({ADMIN_EMAIL}), role: admin.")
        print("The name, email, role, and all other accounts will remain unchanged.")

        # Turn getpass's unsafe echo fallback into an exception instead.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New Admin password (hidden): ")
            confirmation = getpass.getpass("Confirm new password (hidden): ")

        if password != confirmation:
            raise ResetAborted("Passwords do not match. No password was updated.")

        # Reuse the current registration field's length constraints and case rule.
        # Do not construct a public registration request or permit Admin signup.
        password_type = TypeAdapter(Annotated[str, RegisterRequest.model_fields["password"]])
        try:
            password_type.validate_python(password)
        except ValidationError:
            raise ResetAborted(
                "Password must contain 8–128 characters. No password was updated."
            ) from None
        try:
            RegisterRequest.password_contains_both_cases(password)
        except ValueError:
            raise ResetAborted(
                "Password must contain at least one uppercase letter (A-Z) and "
                "one lowercase letter (a-z). No password was updated."
            ) from None

        if input("Type RESET PASSWORD to confirm, or anything else to cancel: ") != "RESET PASSWORD":
            raise ResetAborted("Cancelled. No password was updated.")

        new_hash = hash_password(password)
        # Plaintext is used only in process memory for prompting/validation/hashing.
        password = confirmation = None

        table = User.__table__
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                # Lock matching Admin rows and their index gaps until commit.
                # Concurrent resets cannot change the account during verification.
                admins = connection.execute(
                    select(table).where(table.c.role == "admin").with_for_update()
                ).mappings().all()
                if len(admins) != 1:
                    raise ResetAborted(
                        "Expected exactly one existing Admin. No password was updated."
                    )
                before = dict(admins[0])
                if (
                    before["name"] != ADMIN_NAME
                    or before["email"] != ADMIN_EMAIL
                    or before["role"] != "admin"
                ):
                    raise ResetAborted(
                        "The existing Admin does not match the specified name, email, and role. "
                        "No password was updated."
                    )

                # This is the only write: one column of the locked, verified account.
                result = connection.execute(
                    update(table)
                    .where(
                        table.c.id == before["id"],
                        table.c.email == ADMIN_EMAIL,
                        table.c.role == "admin",
                    )
                    .values(password_hash=new_hash)
                )
                if result.rowcount != 1:
                    raise ResetAborted("Update did not affect exactly one account. Changes rolled back.")

                after = dict(connection.execute(
                    select(table).where(table.c.id == before["id"])
                ).mappings().one())
                if after["password_hash"] != new_hash or any(
                    after[key] != value for key, value in before.items() if key != "password_hash"
                ):
                    raise ResetAborted("Account verification failed. Changes rolled back.")
                commit_attempted = True
            # Success is reported only after the transaction context commits.

        print(f"Password updated successfully for {ADMIN_EMAIL} (admin).")
        return 0
    except ResetAborted as error:
        print(str(error))
        return 1
    except (KeyboardInterrupt, EOFError):
        print(
            "Reset interrupted during commit. Verify the account before retrying."
            if commit_attempted else "Cancelled. No password update was committed."
        )
        return 1
    except getpass.GetPassWarning:
        print("Hidden password entry is unavailable. No password was updated.")
        return 1
    except Exception:
        # Never print exceptions: they may contain credentials or SQL parameters.
        print(
            "Commit could not be confirmed. Verify the account before retrying."
            if commit_attempted else "Reset failed. No password update was committed."
        )
        return 1
    finally:
        password = confirmation = None
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
