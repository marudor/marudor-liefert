from orator.migrations import Migration
from orator.schema.blueprint import Blueprint


class CreateOpportunitiesTable(Migration):
    def up(self):
        """
        Run the migrations.
        """
        with self.schema.create("opportunities") as table:  # type: Blueprint
            table.increments("id")

            table.string("city")
            table.string("date")

            table.timestamps()

    def down(self):
        """
        Revert the migrations.
        """
        self.schema.drop_if_exists("opportunities")
