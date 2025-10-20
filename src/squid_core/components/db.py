from ..logging import get_framework_logger
from tortoise import Tortoise, fields

class Database:

    def __init__(self, url: str):
        self.url = url
        self.logger = get_framework_logger("db")
        self.active = False
        self._models = []
        
    def register_model(self, model_path: str) -> None:
        """Register a model module path for Tortoise ORM."""
        self._models.append(model_path)
        self.logger.info(f"Registered model module: {model_path}")
    
    async def init(self) -> None:
        """Initialize the database connection."""
        if self.active:
            raise RuntimeError("Database connection is already initialized. Cannot re-initialize until closed.")
        self.logger.info(f"Initializing database connection with {len(self._models)} models...")
        await Tortoise.init(db_url=self.url, modules={"models": self._models})
        await Tortoise.generate_schemas(safe=True)
        self.active = True
        self.logger.info("Database connection initialized.")
        
    async def close(self) -> None:
        """Close the database connection."""
        if not self.active:
            self.logger.warning("Database connection is not active. Cannot close.")
            return
        self.logger.info("Closing database connection...")
        await Tortoise.close_connections()
        self.active = False
        self.logger.info("Database connection closed.")