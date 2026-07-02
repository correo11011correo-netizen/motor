import logging
from typing import Optional, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Configuración de logging para el motor
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EvolutionMotor.DB")


class DatabaseManager:
    """
    Gestor de Conexiones Dinámico para el Motor Evolution.
    Permite que el sistema arranque sin base de datos y se vincule
    en caliente mediante una URL (la variante).
    """

    def __init__(self):
        self._engine = None
        self._SessionLocal = None
        self._is_connected = False
        self._current_url = None

    def update_connection(self, db_url: str) -> bool:
        """
        Cierra cualquier conexión existente e intenta vincularse
        a una nueva base de datos mediante la URL proporcionada.
        """
        logger.info(f"Attempting to link to database variant: {db_url}")

        # 1. Limpiar conexión anterior si existe
        self.disconnect()

        try:
            # 2. Crear nuevo engine
            self._engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)
            self._SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self._engine
            )

            # 3. Validar conexión inmediata
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self._current_url = db_url
            self._is_connected = True
            logger.info("Successfully linked to the database variant.")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Failed to link to database variant: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        """Cierra la conexión actual y devuelve el sistema al estado Disconnected."""
        if self._engine:
            self._engine.dispose()
        self._engine = None
        self._SessionLocal = None
        self._is_connected = False
        self._current_url = None
        logger.info("System returned to DISCONNECTED state.")

    def get_session(self) -> Session:
        """
        Retorna una sesión de DB.
        Lanza ConnectionError si el sistema no ha sido vinculado aún.
        """
        if not self._SessionLocal:
            raise ConnectionError(
                "SaaS Motor is currently DISCONNECTED. Please link a DB via Evolution Control Center."
            )

        return self._SessionLocal()

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def current_url(self) -> Optional[str]:
        return self._current_url


# Singleton instance para todo el motor de evolution/saas
db_manager = DatabaseManager()


def get_db() -> Generator[Optional[Session], None, None]:
    """FastAPI dependency to provide DB sessions."""
    try:
        session = db_manager.get_session()
        try:
            yield session
        finally:
            session.close()
    except ConnectionError as e:
        logger.error(f"Database access denied: {e}")
        yield None
