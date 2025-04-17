import lancedb
from mem0.vector_stores.base import VectorStoreBase

class LanceDB(VectorStoreBase):
    def __init__(
        self,
        uri: str,
        table_name: str = "vectorstore",
        id_key: str = "id",
        vector_key: str = "vector",
        distance_metric: str = "L2",
        **kwargs,
    ):
        # Connect to LanceDB
        self.db = lancedb.connect(uri)  # :contentReference[oaicite:2]{index=2}
        # Create or open table
        if table_name in self.db.list_tables():
            self.table = self.db.open_table(table_name)
        else:
            self.table = self.db.create_table(
                table_name,
                data=[],
                mode="overwrite"
            )
        self.id_key = id_key
        self.vector_key = vector_key

    def insert(self, vectors: list[list[float]], payloads: list[dict] = None, ids: list[str] = None):
        # Prepare records: dicts mapping id_key, vector_key, and metadata
        docs = []
        for i, vec in enumerate(vectors):
            record = {
                self.vector_key: vec,
                self.id_key: ids[i] if ids else i,
            }
            if payloads:
                record.update(payloads[i])
            docs.append(record)
        self.table.add(docs)  # Table.add handles upserts, nan‑dropping, etc. :contentReference[oaicite:3]{index=3}

    def search(self, query_vector: list[float], limit: int = 10, filters: dict = None) -> list:
        qb = self.table.search(
            query_vector,
            vector_column_name=self.vector_key,
            limit=limit,
        )
        # Apply SQL filters if any (lancedb.search().where(...))
        if filters:
            # e.g. qb = qb.where("field = value", prefilter=True)
            for expr in filters.get("sql_expressions", []):
                qb = qb.where(expr, prefilter=True)
        return qb.to_pandas().to_dict(orient="records")

    def delete(self, vector_id: str):
        self.table.delete(vector_id)  # LanceDB supports delete by id :contentReference[oaicite:4]{index=4}

    def update(self, vector_id: str, vector: list[float] = None, payload: dict = None):
        # In LanceDB, .add() with overwrite achieves update
        rec = {self.id_key: vector_id}
        if vector is not None:
            rec[self.vector_key] = vector
        if payload:
            rec.update(payload)
        self.table.add([rec])  

    def list(self, limit: int = 100):
        # Simple full scan
        return self.table.to_pandas().head(limit).to_dict(orient="records")
