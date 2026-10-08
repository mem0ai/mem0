"""Amazon Bedrock Knowledge Base as a vector store backend for Mem0.

Uses Bedrock Managed Knowledge Bases for storage and retrieval.
Write operations upload to the KB's S3 data source and trigger ingestion sync.
"""

import os
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: str
    score: float
    payload: Dict


def _get_source_uri(result: dict) -> str:
    """Extract source URI from a retrieval result, handling all location types."""
    location = result.get('location', {})
    loc_type = location.get('type', '')
    if loc_type == 'S3' or 's3Location' in location:
        return location.get('s3Location', {}).get('uri', '')
    elif loc_type == 'WEB' or 'webLocation' in location:
        return location.get('webLocation', {}).get('url', '')
    elif 'confluenceLocation' in location:
        return location.get('confluenceLocation', {}).get('url', '')
    elif 'salesforceLocation' in location:
        return location.get('salesforceLocation', {}).get('url', '')
    elif 'sharePointLocation' in location:
        return location.get('sharePointLocation', {}).get('url', '')
    elif 'customDocumentLocation' in location:
        return location.get('customDocumentLocation', {}).get('id', '')
    # Fallback to metadata._source_uri (for agentic results)
    return result.get('metadata', {}).get('_source_uri', '')


class BedrockKB(VectorStoreBase):
    """Amazon Bedrock Knowledge Base vector store backend.

    Args:
        knowledge_base_id: The KB ID. Falls back to KNOWLEDGE_BASE_ID env var.
        data_source_id: The data source ID for ingestion. Falls back to BEDROCK_DATA_SOURCE_ID env var.
        data_source_bucket: S3 bucket for the KB's data source. Falls back to BEDROCK_DATA_SOURCE_BUCKET env var.
        region_name: AWS region. Falls back to AWS_REGION env var or us-east-1.
        number_of_results: Default number of results. Defaults to 5.
        knowledge_base_type: 'MANAGED' (recommended) or 'VECTOR'.
        use_agentic_retrieval: If True, try AgenticRetrieveStream first with fallback to plain Retrieve.
        data_source_type: 'S3' (default, uses S3 upload + sync) or 'CUSTOM' (uses IngestKnowledgeBaseDocuments API, no S3 needed).
    """

    def __init__(
        self,
        knowledge_base_id: Optional[str] = None,
        data_source_id: Optional[str] = None,
        data_source_bucket: Optional[str] = None,
        region_name: Optional[str] = None,
        number_of_results: int = 5,
        knowledge_base_type: str = "MANAGED",
        use_agentic_retrieval: Optional[bool] = None,
        data_source_type: str = "S3",
    ):
        self.knowledge_base_id = knowledge_base_id or os.environ.get("KNOWLEDGE_BASE_ID", "")
        self.data_source_id = data_source_id or os.environ.get("BEDROCK_DATA_SOURCE_ID", "")
        self.data_source_bucket = data_source_bucket or os.environ.get("BEDROCK_DATA_SOURCE_BUCKET", "")
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self.number_of_results = number_of_results
        self.knowledge_base_type = knowledge_base_type
        self.use_agentic_retrieval = use_agentic_retrieval if use_agentic_retrieval is not None else os.environ.get('USE_AGENTIC_RETRIEVAL', 'true').lower() != 'false'
        self.data_source_type = data_source_type or os.environ.get("BEDROCK_DATA_SOURCE_TYPE", "S3").upper()
        self._runtime_client = None
        self._agent_client = None
        self._s3_client = None

    @property
    def runtime_client(self):
        if self._runtime_client is None:
            import boto3
            from botocore.config import Config
            self._runtime_client = boto3.client(
                "bedrock-agent-runtime",
                region_name=self.region_name,
                config=Config(user_agent_extra="mem0/bedrock-kb"),
            )
        return self._runtime_client

    @property
    def agent_client(self):
        if self._agent_client is None:
            import boto3
            from botocore.config import Config
            self._agent_client = boto3.client(
                "bedrock-agent",
                region_name=self.region_name,
                config=Config(user_agent_extra="mem0/bedrock-kb"),
            )
        return self._agent_client

    @property
    def s3_client(self):
        if self._s3_client is None:
            import boto3
            from botocore.config import Config
            self._s3_client = boto3.client(
                "s3",
                region_name=self.region_name,
                config=Config(user_agent_extra="mem0/bedrock-kb"),
            )
        return self._s3_client

    def create_col(self, name, vector_size, distance):
        """Not needed — KB is pre-created via AWS console or API."""
        logger.info("Bedrock KB is managed externally. No collection creation needed.")

    def insert(self, vectors, payloads=None, ids=None):
        """Insert documents into the knowledge base.

        Uses IngestKnowledgeBaseDocuments (CUSTOM) or S3 upload + sync (S3) based on data_source_type.
        """
        if self.data_source_type == "CUSTOM":
            return self._insert_direct(payloads, ids)
        else:
            return self._insert_s3(payloads, ids)

    def _insert_direct(self, payloads=None, ids=None):
        """Insert documents directly via IngestKnowledgeBaseDocuments API (CUSTOM data source).

        Supports two modes based on payload content:
        - Inline text: payload = {"data": "text content", "metadata": {...}}
        - S3 reference: payload = {"s3_uri": "s3://bucket/key", "metadata": {...}}
        - Binary/file: payload = {"data": base64_bytes, "mime_type": "application/pdf", "metadata": {...}}
        """
        if not self.data_source_id:
            logger.warning("No data_source_id configured. Cannot insert.")
            return None

        import mimetypes

        inserted_ids = []
        documents = []
        for i, payload in enumerate(payloads or []):
            doc_id = ids[i] if ids else str(uuid.uuid4())
            metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}

            # Determine content type: S3 reference, binary, or inline text
            if isinstance(payload, dict) and "s3_uri" in payload:
                # S3 reference — point to existing file in S3
                doc = {
                    "content": {
                        "dataSourceType": "CUSTOM",
                        "custom": {
                            "customDocumentIdentifier": {"id": doc_id},
                            "sourceType": "S3_LOCATION",
                            "s3Location": {"uri": payload["s3_uri"]},
                        },
                    },
                }
            elif isinstance(payload, dict) and "mime_type" in payload:
                # Binary content (base64)
                doc = {
                    "content": {
                        "dataSourceType": "CUSTOM",
                        "custom": {
                            "customDocumentIdentifier": {"id": doc_id},
                            "sourceType": "IN_LINE",
                            "inlineContent": {
                                "type": "BYTE",
                                "byteContent": {
                                    "data": payload.get("data", ""),
                                    "mimeType": payload["mime_type"],
                                },
                            },
                        },
                    },
                }
            else:
                # Inline text (default)
                content = payload.get("data", "") if isinstance(payload, dict) else str(payload)
                doc = {
                    "content": {
                        "dataSourceType": "CUSTOM",
                        "custom": {
                            "customDocumentIdentifier": {"id": doc_id},
                            "sourceType": "IN_LINE",
                            "inlineContent": {
                                "type": "TEXT",
                                "textContent": {"data": content},
                            },
                        },
                    },
                }

            # Add metadata as inline attributes
            if metadata:
                doc["metadata"] = {
                    "type": "IN_LINE_ATTRIBUTE",
                    "inlineAttributes": [
                        {"key": k, "value": {"stringValue": str(v), "type": "STRING"}}
                        for k, v in metadata.items()
                    ],
                }

            documents.append(doc)
            inserted_ids.append(doc_id)

            # API allows max 10 docs per call
            if len(documents) >= 10:
                self._ingest_documents(documents)
                documents = []

        if documents:
            self._ingest_documents(documents)

        return inserted_ids

    def _ingest_documents(self, documents):
        """Call IngestKnowledgeBaseDocuments API."""
        try:
            self.agent_client.ingest_knowledge_base_documents(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
                documents=documents,
            )
        except Exception as e:
            logger.error(f"Error ingesting documents directly: {e}")

    def _insert_s3(self, payloads=None, ids=None):
        """Insert documents by uploading to S3 and triggering ingestion."""
        if not self.data_source_bucket:
            logger.warning("No data_source_bucket configured. Cannot insert.")
            return None

        inserted_ids = []
        for i, payload in enumerate(payloads or []):
            doc_id = ids[i] if ids else str(uuid.uuid4())
            content = payload.get("data", "") if isinstance(payload, dict) else str(payload)
            metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}

            # Use user_id in key path for tenant isolation
            user_id = metadata.get("user_id", "_default")
            key = f"mem0/{user_id}/{doc_id}.txt"

            # Upload document to S3
            self.s3_client.put_object(
                Bucket=self.data_source_bucket,
                Key=key,
                Body=content,
            )

            # Upload metadata sidecar for filtering
            import json
            meta_attrs = {"user_id": user_id, "mem0_id": doc_id}
            meta_attrs.update({k: str(v) for k, v in metadata.items()})
            metadata_content = json.dumps({
                "metadataAttributes": {k: v for k, v in meta_attrs.items()}
            })
            self.s3_client.put_object(
                Bucket=self.data_source_bucket,
                Key=f"{key}.metadata.json",
                Body=metadata_content,
            )
            inserted_ids.append(doc_id)

        # Trigger ingestion sync
        if inserted_ids and self.data_source_id:
            self._start_ingestion()

        return inserted_ids

    def _agentic_retrieve(self, query: str, top_k: int):
        """Try agentic retrieval with streaming. Returns list of results or None on failure."""
        try:
            response = self.runtime_client.agentic_retrieve_stream(
                knowledgeBaseId=self.knowledge_base_id,
                messages=[{"content": {"text": query}, "role": "user"}],
                retrievers=[{
                    "configuration": {
                        "knowledgeBase": {
                            "knowledgeBaseId": self.knowledge_base_id,
                            "retrievalOverrides": {"maxNumberOfResults": top_k},
                        }
                    }
                }],
                agenticRetrieveConfiguration={
                    "foundationModelType": "MANAGED",
                    "rerankingModelType": "MANAGED",
                },
            )
            results = []
            for event in response.get("stream", []):
                if "result" in event and "results" in event["result"]:
                    for result in event["result"]["results"]:
                        content = result.get("content", {}).get("text", "")
                        source = _get_source_uri(result)
                        score = result.get("score", 0.0)
                        # Extract doc_id from source URI (mem0/{doc_id}.txt pattern)
                        doc_id = source.split("/")[-1].replace(".txt", "") if source else str(uuid.uuid4())
                        results.append(OutputData(
                            id=doc_id,
                            score=score,
                            payload={"data": content, "source": source},
                        ))
            return results
        except Exception as e:
            logger.debug(f"Agentic retrieval unavailable, will fall back to managed retrieve: {e}")
            return None

    def search(self, query, vectors=None, top_k=5, filters=None):
        """Search the knowledge base. Tries agentic retrieval first if enabled."""
        # Try agentic retrieval first (skip when filters are provided — agentic doesn't support metadata filtering)
        if self.use_agentic_retrieval and not filters:
            agentic_results = self._agentic_retrieve(query, top_k)
            if agentic_results is not None:
                return agentic_results

        # Fallback to managed/vector retrieve
        if self.knowledge_base_type == "MANAGED":
            retrieval_config = {"managedSearchConfiguration": {"numberOfResults": top_k}}
            # Apply metadata filter for tenant isolation
            if filters:
                filter_conditions = []
                for key, value in filters.items():
                    filter_conditions.append({"equals": {"key": key, "value": value}})
                if len(filter_conditions) == 1:
                    retrieval_config["managedSearchConfiguration"]["filter"] = filter_conditions[0]
                else:
                    retrieval_config["managedSearchConfiguration"]["filter"] = {"andAll": filter_conditions}
        else:
            retrieval_config = {"vectorSearchConfiguration": {"numberOfResults": top_k}}
            if filters:
                filter_conditions = []
                for key, value in filters.items():
                    filter_conditions.append({"equals": {"key": key, "value": value}})
                if len(filter_conditions) == 1:
                    retrieval_config["vectorSearchConfiguration"]["filter"] = filter_conditions[0]
                else:
                    retrieval_config["vectorSearchConfiguration"]["filter"] = {"andAll": filter_conditions}

        try:
            response = self.runtime_client.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration=retrieval_config,
            )
            results = []
            for result in response.get("retrievalResults", []):
                content = result.get("content", {}).get("text", "")
                source = _get_source_uri(result)
                score = result.get("score", 0.0)
                # Extract doc_id from source URI (mem0/{doc_id}.txt pattern)
                doc_id = source.split("/")[-1].replace(".txt", "") if source else str(uuid.uuid4())
                results.append(OutputData(
                    id=doc_id,
                    score=score,
                    payload={"data": content, "source": source},
                ))
            return results
        except Exception as e:
            logger.error(f"Error searching Bedrock KB: {e}")
            return []

    def delete(self, vector_id, filters=None):
        """Delete a document by removing from S3 and triggering re-sync."""
        if not self.data_source_bucket:
            logger.warning("No data_source_bucket configured. Cannot delete.")
            return

        user_id = filters.get("user_id", "_default") if filters else "_default"
        key = f"mem0/{user_id}/{vector_id}.txt"
        try:
            self.s3_client.delete_object(Bucket=self.data_source_bucket, Key=key)
            self.s3_client.delete_object(Bucket=self.data_source_bucket, Key=f"{key}.metadata.json")
            if self.data_source_id:
                self._start_ingestion()
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")

    def update(self, vector_id, vector=None, payload=None, filters=None):
        """Update by re-uploading to S3 and triggering sync."""
        if payload and self.data_source_bucket:
            content = payload.get("data", "") if isinstance(payload, dict) else str(payload)
            metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
            user_id = metadata.get("user_id", filters.get("user_id", "_default") if filters else "_default")
            key = f"mem0/{user_id}/{vector_id}.txt"
            self.s3_client.put_object(
                Bucket=self.data_source_bucket,
                Key=key,
                Body=content,
            )
            # Update metadata sidecar
            import json
            meta_attrs = {"user_id": user_id, "mem0_id": vector_id}
            meta_attrs.update({k: str(v) for k, v in metadata.items()})
            self.s3_client.put_object(
                Bucket=self.data_source_bucket,
                Key=f"{key}.metadata.json",
                Body=json.dumps({"metadataAttributes": {k: v for k, v in meta_attrs.items()}}),
            )
            if self.data_source_id:
                self._start_ingestion()

    def get(self, vector_id, filters=None):
        """Get a document from S3 by ID."""
        if not self.data_source_bucket:
            return None
        user_id = filters.get("user_id", "_default") if filters else "_default"
        key = f"mem0/{user_id}/{vector_id}.txt"
        try:
            response = self.s3_client.get_object(Bucket=self.data_source_bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            return OutputData(id=vector_id, score=0.0, payload={"data": content})
        except Exception:
            return None

    def list_cols(self):
        """List knowledge bases."""
        try:
            response = self.agent_client.list_knowledge_bases()
            return [kb["name"] for kb in response.get("knowledgeBaseSummaries", [])]
        except Exception as e:
            logger.error(f"Error listing KBs: {e}")
            return []

    def delete_col(self):
        """Not supported — KB deletion should be done via AWS console."""
        logger.warning("KB deletion not supported via this interface. Use AWS console.")

    def col_info(self):
        """Get KB info."""
        try:
            response = self.agent_client.get_knowledge_base(knowledgeBaseId=self.knowledge_base_id)
            kb = response["knowledgeBase"]
            return {"name": kb["name"], "status": kb["status"], "type": self.knowledge_base_type}
        except Exception as e:
            logger.error(f"Error getting KB info: {e}")
            return {}

    def list(self, filters=None, top_k=None):
        """List documents by listing S3 objects in the data source prefix."""
        if not self.data_source_bucket:
            return [[]]
        try:
            # Scope by user_id if provided in filters
            user_id = filters.get("user_id", "") if filters else ""
            prefix = f"mem0/{user_id}/" if user_id else "mem0/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.data_source_bucket, Prefix=prefix, MaxKeys=top_k or 100
            )
            results = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".metadata.json"):
                    continue  # Skip metadata sidecar files
                # Extract doc_id from path: mem0/{user_id}/{doc_id}.txt
                doc_id = key.split("/")[-1].replace(".txt", "")
                results.append(OutputData(
                    id=doc_id,
                    score=0.0,
                    payload={"key": obj["Key"]},
                ))
            return [results]
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return [[]]

    def reset(self):
        """Reset by clearing all documents from the S3 data source prefix."""
        if not self.data_source_bucket:
            logger.warning("No data_source_bucket configured. Cannot reset.")
            return
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.data_source_bucket, Prefix="mem0/")
            for obj in response.get("Contents", []):
                self.s3_client.delete_object(Bucket=self.data_source_bucket, Key=obj["Key"])
            if self.data_source_id:
                self._start_ingestion()
        except Exception as e:
            logger.error(f"Error resetting KB data: {e}")

    def _start_ingestion(self):
        """Trigger a data source ingestion job."""
        try:
            self.agent_client.start_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
            )
            logger.info(f"Ingestion job started for KB {self.knowledge_base_id}")
        except Exception as e:
            logger.error(f"Error starting ingestion: {e}")
