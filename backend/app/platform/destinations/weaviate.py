"""Weaviate destination implementation."""

from typing import List
from uuid import UUID

from weaviate.collections import Collection
from weaviate.collections.classes.config import DataType, Property

from app import schemas
from app.platform.auth.schemas import AuthType, WeaviateAuthCredentials
from app.platform.chunks._base import BaseChunk
from app.platform.decorators import destination
from app.platform.destinations._base import BaseDestination
from app.platform.embedding_models._adapters import WeaviateModelAdapter
from app.platform.embedding_models._base import BaseEmbeddingModel
from app.vector_db.weaviate_service import WeaviateService


@destination("Weaviate", "weaviate", AuthType.url_and_api_key)
class WeaviateDestination(BaseDestination):
    """Weaviate destination implementation."""

    def __init__(self):
        """Initialize Weaviate destination."""
        self.collection: Collection | None = None
        self.sync_id: UUID | None = None
        self.embedding_model: BaseEmbeddingModel | None = None
        self.collection_name: str | None = None
        self.cluster_url: str | None = None
        self.api_key: str | None = None

    @classmethod
    async def create(
        cls,
        user: schemas.User,
        sync_id: UUID,
        embedding_model: BaseEmbeddingModel,
    ) -> "WeaviateDestination":
        """Create a new Weaviate destination.

        Args:
            user (schemas.User): The user creating the destination.
            sync_id (UUID): The ID of the sync.
            embedding_model (BaseEmbeddingModel): The embedding model to use.

        Returns:
            WeaviateDestination: The created destination.
        """
        instance = cls()
        instance.sync_id = sync_id
        instance.collection_name = f"Chunks_{instance._sanitize_collection_name(sync_id)}"
        instance.embedding_model = embedding_model

        # Get credentials for sync_id
        credentials = await cls.get_credentials(sync_id)
        if credentials:
            instance.cluster_url = credentials.cluster_url
            instance.api_key = credentials.api_key
        else:
            instance.cluster_url = None
            instance.api_key = None

        # Set up initial collection
        await instance.setup_collection(sync_id)
        return instance

    async def get_credentials(sync_id: UUID) -> WeaviateAuthCredentials | None:
        """Get credentials for sync_id.

        Args:
            sync_id (UUID): The ID of the sync.

        Returns:
            WeaviateAuthCredentials | None: The credentials for the sync.
        """
        # TODO: Implement this
        return None

    async def setup_collection(self, sync_id: UUID) -> None:
        """Set up the Weaviate collection for storing chunks.

        Args:
            sync_id (UUID): The ID of the sync.
        """
        if not self.embedding_model:
            raise ValueError("Embedding model not configured")

        properties = [
            Property(name="source_name", data_type=DataType.TEXT),
            Property(name="entity_id", data_type=DataType.TEXT),
            Property(name="sync_id", data_type=DataType.TEXT),
            Property(name="content", data_type=DataType.TEXT),
            Property(name="url", data_type=DataType.TEXT),
            Property(
                name="breadcrumbs",
                data_type=DataType.OBJECT_ARRAY,
                nested_properties=[
                    Property(name="entity_id", data_type=DataType.TEXT),
                    Property(name="name", data_type=DataType.TEXT),
                    Property(name="type", data_type=DataType.TEXT),
                ],
            ),
        ]

        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            try:
                self.collection = await service.create_weaviate_collection(
                    collection_name=self.collection_name,
                    properties=properties,
                    vectorizer_config=WeaviateModelAdapter.get_vectorizer_config(self.embedding_model),
                    generative_config=WeaviateModelAdapter.get_generative_config(self.embedding_model),
                )
            except Exception as e:
                if "already exists" not in str(e):
                    raise
                self.collection = await service.get_weaviate_collection(self.collection_name)

    async def bulk_insert(self, chunks: List[BaseChunk]) -> None:
        """Bulk insert chunks into Weaviate."""
        if not chunks or not self.embedding_model:
            return

        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            collection = await service.get_weaviate_collection(self.collection_name)

            # Transform chunks into the format Weaviate expects
            objects_to_insert = []
            for chunk in chunks:
                # Use model_dump() to get all fields including from subclasses
                data_object = chunk.model_dump()
                objects_to_insert.append(data_object)

            # Bulk insert using modern client
            response = await collection.data.insert_many(objects_to_insert)

            if response.errors:
                raise Exception("Errors during bulk insert: %s", response.errors)

    async def bulk_delete(self, chunk_ids: List[UUID]) -> None:
        """Bulk delete chunks from Weaviate.

        Args:
            chunk_ids (List[UUID]): The IDs of the chunks to delete.
        """
        if not chunk_ids:
            return

        async with WeaviateService() as service:
            collection = await service.get_weaviate_collection(self.collection_name)

            for chunk_id in chunk_ids:
                try:
                    # Delete using deterministic UUID
                    await collection.objects.delete(uuid=f"{chunk_id}_{self.sync_id}")
                except Exception as e:
                    if "not found" not in str(e).lower():
                        raise

    @staticmethod
    def _sanitize_collection_name(collection_name: UUID) -> str:
        """Sanitize the collection name to be a valid Weaviate collection name.

        Args:
            collection_name (UUID): The collection name to sanitize.

        Returns:
            str: The sanitized collection name.
        """
        return str(collection_name).replace("-", "_")
