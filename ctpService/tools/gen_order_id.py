# -*- coding:utf-8 -*-

import redis

client = redis.Redis(host='localhost', port=6379)
order_id_key = 'UNIQUE_ORDER_ID'


def gen_order_id(max_id):
    for order in range(1, max_id):
        yield str(order)


def push_to_memory(order_id):
    print('add order_id {}'.format(order_id))
    client.rpush(order_id_key, *[order_id])


if __name__ == '__main__':
    order_gen = gen_order_id(10000)
    for oid in order_gen:
        push_to_memory(oid)
