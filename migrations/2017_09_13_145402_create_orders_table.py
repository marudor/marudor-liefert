from orator.migrations import Migration
from orator.schema.blueprint import Blueprint


class CreateOrdersTable(Migration):
    def up(self):
        """
        Run the migrations.
        """
        with self.schema.create("orders") as table:  # type: Blueprint
            table.increments("id")

            table.integer("user_id").unsigned()
            table.integer("opportunity_id").unsigned()
            table.text("order_text")

            table.timestamps()

            table.unique(["user_id", "opportunity_id"])

    def down(self):
        """
        Revert the migrations.
        """
        self.schema.drop_if_exists("orders")
