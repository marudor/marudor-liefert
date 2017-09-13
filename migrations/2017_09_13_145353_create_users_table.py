from orator.migrations import Migration
from orator.schema.blueprint import Blueprint


class CreateUsersTable(Migration):
    def up(self):
        """
        Run the migrations.
        """
        with self.schema.create("users") as table:  # type: Blueprint
            table.increments("id")

            table.integer("telegram_user_id").unsigned().unique()
            table.string("telegram_username")
            table.string("hometown")

            table.timestamps()

    def down(self):
        """
        Revert the migrations.
        """
        self.schema.drop_if_exists("users")
