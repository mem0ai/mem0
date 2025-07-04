import os
import random

import uuid

import pytest

from tablestore_for_agent_memory.util.tablestore_helper import TablestoreHelper

from mem0.vector_stores.aliyun_tablestore import AliyunTableStore, OutputData

@pytest.fixture
def aliyun_tablestore_instance():
    return AliyunTableStore(
        endpoint=os.environ["TABLESTORE_ENDPOINT"],
        instance_name=os.environ["TABLESTORE_INSTANCE_NAME"],
        access_key_id=os.environ["TABLESTORE_ACCESS_KEY_ID"],
        access_key_secret=os.environ["TABLESTORE_ACCESS_KEY_SECRET"],
        vector_dimension=4,
        collection_name='test_collection',
        search_index_name='test_search_index',
    )

def wait_for_index_ready(aliyun_tablestore_instance: AliyunTableStore, length):
    TablestoreHelper.wait_search_index_ready(
        tablestore_client=aliyun_tablestore_instance._tablestore_client,
        table_name=aliyun_tablestore_instance._collection_name,
        index_name=aliyun_tablestore_instance._search_index_name,
        total_count=length,
    )

@pytest.fixture
def data():
    vectors = [[0.1, 0.2, 0.3, 0.4]]
    payloads = [{"data": "aaa", "role": "user"}]
    ids = ["id1"]
    return vectors, payloads, ids

def random_data():
    vector = [random.random() for _ in range(4)]
    rand_text = " ".join(
        random.choices(
            ["abc", "def", "ghi", "abcd", "adef", "abcgh", "apple", "banana", "cherry"], k=random.randint(1, 10)
        )
    )
    rand_role = random.choices(["user", "assistant"])[0]
    payload = {"data": rand_text, "role": rand_role}
    id = str(uuid.uuid4())
    return vector, payload, id

def batch_data(length: int):
    vectors = []
    payloads = []
    ids = []
    for _ in range(length):
        vector, payload, id = random_data()
        vectors.append(vector)
        payloads.append(payload)
        ids.append(id)
    return vectors, payloads, ids

def test_init(aliyun_tablestore_instance):
    assert aliyun_tablestore_instance._collection_name in aliyun_tablestore_instance.list_cols()

def test_list(aliyun_tablestore_instance):
    length = 100

    vectors, payloads, ids = batch_data(length)
    aliyun_tablestore_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    # 等待索引表准备完毕，防止出现不在预期内结果
    wait_for_index_ready(aliyun_tablestore_instance, length)

    outputs = aliyun_tablestore_instance.list()[0]
    assert len(outputs) == length

    user_count = 0
    for payload in payloads:
        if payload["role"] == "user":
            user_count += 1

    user_filters = {'role': 'user'}

    outputs = aliyun_tablestore_instance.list(filters=user_filters)[0]
    assert all(
        [
            output.payload["role"] == "user"
            for output in outputs
        ]
    )
    assert len(outputs) == user_count

    half_length = length // 2
    outputs = aliyun_tablestore_instance.list(limit=half_length)[0]
    assert len(outputs) == half_length

    half_user_count = user_count // 2
    outputs = aliyun_tablestore_instance.list(filters=user_filters, limit=half_user_count)[0]
    assert all(
        [
            output.payload["role"] == "user"
            for output in outputs
        ]
    )
    assert len(outputs) == half_user_count

    # reset防止影响其他用例
    aliyun_tablestore_instance.reset()

def test_insert_and_reset(aliyun_tablestore_instance, data):
    vectors, payloads, ids = data

    aliyun_tablestore_instance.insert(vectors=vectors, payloads=payloads, ids=ids)
    wait_for_index_ready(aliyun_tablestore_instance, len(ids))
    outputs = aliyun_tablestore_instance.list()[0]

    assert len(outputs) == 1
    assert isinstance(outputs[0], OutputData)

    assert outputs[0].id == ids[0]
    assert outputs[0].payload == payloads[0]

    aliyun_tablestore_instance.reset()
    assert aliyun_tablestore_instance._collection_name in aliyun_tablestore_instance.list_cols()

    wait_for_index_ready(aliyun_tablestore_instance, 0)
    outputs = aliyun_tablestore_instance.list()[0]
    assert len(outputs) == 0

    length = 100
    vectors, payloads, ids = batch_data(length)
    aliyun_tablestore_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    wait_for_index_ready(aliyun_tablestore_instance, length)
    outputs = aliyun_tablestore_instance.list()[0]
    assert len(outputs) == length

    aliyun_tablestore_instance.reset()

def test_delete(aliyun_tablestore_instance, data):
    vectors, payloads, ids = data
    aliyun_tablestore_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    aliyun_tablestore_instance.delete(ids[0])

    wait_for_index_ready(aliyun_tablestore_instance, 0)
    outputs = aliyun_tablestore_instance.list()[0]
    assert len(outputs) == 0

def test_update(aliyun_tablestore_instance, data):
    vectors, payloads, ids = data
    aliyun_tablestore_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    update_payload = {"data": "bbb", "role": "user"}

    aliyun_tablestore_instance.update(vector_id=ids[0], payload=update_payload)
    wait_for_index_ready(aliyun_tablestore_instance, len(ids))
    outputs = aliyun_tablestore_instance.list()[0]

    assert outputs[0].payload == update_payload

    aliyun_tablestore_instance.delete(ids[0])

def test_get(aliyun_tablestore_instance, data):
    vectors, payloads, ids = data
    aliyun_tablestore_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    output = aliyun_tablestore_instance.get(ids[0])
    assert output.payload == payloads[0]

    aliyun_tablestore_instance.delete(ids[0])

def test_delete_col_and_create_col(aliyun_tablestore_instance):
    aliyun_tablestore_instance.delete_col()
    assert aliyun_tablestore_instance._collection_name not in aliyun_tablestore_instance.list_cols()

    aliyun_tablestore_instance.create_col()
    assert aliyun_tablestore_instance._collection_name in aliyun_tablestore_instance.list_cols()

def test_search(aliyun_tablestore_instance):
    length = 100
    vectors, payloads, ids = batch_data(length)
    aliyun_tablestore_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    idx = random.choices(range(len(vectors)))[0]
    query_vector, query_payload, id = vectors[idx], payloads[idx], ids[idx]

    outputs = aliyun_tablestore_instance.get(id)
    assert outputs.payload == query_payload

    # 等待索引表准备完毕，防止出现不在预期内结果
    wait_for_index_ready(aliyun_tablestore_instance, length)

    limit_num = 5
    outputs = aliyun_tablestore_instance.search(query=query_payload["data"], vectors=query_vector, limit=limit_num)
    assert id in [output.id for output in outputs]

    half_limit_num = limit_num // 2
    outputs = aliyun_tablestore_instance.search(query=query_payload["data"], vectors=query_vector, limit=half_limit_num)
    assert len(outputs) == half_limit_num

    user_filters = {'role': 'user'}
    outputs = aliyun_tablestore_instance.search(query=query_payload["data"], vectors=query_vector, limit=limit_num, filters=user_filters)
    assert all(
        [
            output.payload["role"] == "user"
            for output in outputs
        ]
    )
    assert len(outputs) == limit_num

    outputs = aliyun_tablestore_instance.search(query=query_payload["data"], vectors=query_vector, limit=half_limit_num, filters=user_filters)
    assert all(
        [
            output.payload["role"] == "user"
            for output in outputs
        ]
    )
    assert len(outputs) == half_limit_num

    aliyun_tablestore_instance.reset()









