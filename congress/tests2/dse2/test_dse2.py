# Copyright (c) 2013 VMware, Styra.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import mock
import novaclient
import time

from oslo_config import cfg
cfg.CONF.distributed_architecture = True
from oslo_messaging import conffixture

from congress.datalog import compile
from congress.datasources.nova_driver import NovaDriver
from congress.dse2.dse_node import DseNode
# TODO(dse2): reenable once reeneabled unregister test
# from congress import exception as congressException
from congress.policy_engines.agnostic import Dse2Runtime
from congress.tests import base
from congress.tests.fake_datasource import FakeDataSource
from congress.tests import helper


class TestDSE(base.TestCase):

    def setUp(self):
        super(TestDSE, self).setUp()
        mc_fixture = conffixture.ConfFixture(cfg.CONF)
        mc_fixture.conf.transport_url = 'kombu+memory://'
        self.messaging_config = mc_fixture.conf
        self.messaging_config.rpc_response_timeout = 1
        self.nodes_to_stop = []

    def tearDown(self):
        for n in self.nodes_to_stop:  # stop all nodes at end of each test
            n.stop()
            n.wait()
        super(TestDSE, self).tearDown()

    # TODO(dse2): Always succeeds when run standalone.
    #   Fails when run in parallel.
    # def test_get_global_service_names(self):
    #     node = DseNode(self.messaging_config, "test", [])
    #     self.nodes_to_stop.append(node)
    #     test1 = FakeDataSource('test1')
    #     test2 = FakeDataSource('test2')
    #     node.register_service(test1)
    #     node.register_service(test2)
    #     actual = set(node.get_global_service_names())
    #     self.assertEqual(actual, set(['test1', 'test2']))

    def test_intranode_pubsub(self):
        node = DseNode(self.messaging_config, "test", [])
        self.nodes_to_stop.append(node)
        test1 = FakeDataSource('test1')
        test2 = FakeDataSource('test2')
        node.register_service(test1)
        node.register_service(test2)

        test1.subscribe('test2', 'p')
        helper.retry_check_function_return_value(
            lambda: hasattr(test1, 'last_msg'), True)
        test2.publish('p', 42)
        helper.retry_check_function_return_value(
            lambda: test1.last_msg['data'], 42)
        self.assertFalse(hasattr(test2, "last_msg"))

    def test_intranode_pubsub2(self):
        # same as test_intranode_pubsub but with opposite ordering.
        # (Ordering does matter with internode_pubsub).
        node = DseNode(self.messaging_config, "test", [])
        self.nodes_to_stop.append(node)
        test1 = FakeDataSource('test1')
        test2 = FakeDataSource('test2')
        node.register_service(test1)
        node.register_service(test2)

        test2.subscribe('test1', 'p')
        helper.retry_check_function_return_value(
            lambda: hasattr(test2, 'last_msg'), True)
        test1.publish('p', 42)
        helper.retry_check_function_return_value(
            lambda: test2.last_msg['data'], 42)
        self.assertFalse(hasattr(test1, "last_msg"))

    def test_intranode_partial_unsub(self):
        node = DseNode(self.messaging_config, "test", [])
        test1 = FakeDataSource('test1')
        test2 = FakeDataSource('test2')
        node.register_service(test1)
        node.register_service(test2)

        test1.subscribe('test2', 'p')
        test1.subscribe('test2', 'q')
        test1.unsubscribe('test2', 'q')  # unsub from q should not affect p
        helper.retry_check_function_return_value(
            lambda: hasattr(test1, 'last_msg'), True)
        test2.publish('p', 42)
        helper.retry_check_function_return_value(
            lambda: test1.last_msg['data'], 42)
        self.assertFalse(hasattr(test2, "last_msg"))

    # TODO(dse2): re-enable once multi-node DSE is working.
    #  This test and the next one were manually merged together--may not
    #  be fully functional.
    #  Before merge: if setup node2 first, works fine.
    def test_internode_pubsub(self):
        node1 = DseNode(self.messaging_config, "testnode1", [])
        test1 = FakeDataSource('test1')
        node1.register_service(test1)
        node2 = DseNode(self.messaging_config, "testnode2", [])
        test2 = FakeDataSource('test2')
        node2.register_service(test2)

        test1.subscribe('test2', 'p')
        helper.retry_check_function_return_value(
            lambda: hasattr(test1, 'last_msg'), True)
        test2.publish('p', 42)
        helper.retry_check_function_return_value(
            lambda: test1.last_msg['data'], 42)
        self.assertFalse(hasattr(test2, "last_msg"))

    def test_internode_partial_unsub(self):
        node1 = DseNode(self.messaging_config, "testnode1", [])
        node2 = DseNode(self.messaging_config, "testnode2", [])
        test1 = FakeDataSource('test1')
        test2 = FakeDataSource('test2')
        node1.register_service(test1)
        node2.register_service(test2)

        test1.subscribe('test2', 'p')
        test1.subscribe('test2', 'q')
        test1.unsubscribe('test2', 'q')  # unsub from q should not affect p
        helper.retry_check_function_return_value(
            lambda: hasattr(test1, 'last_msg'), True)
        test2.publish('p', 42)
        helper.retry_check_function_return_value(
            lambda: test1.last_msg['data'], 42)
        self.assertFalse(hasattr(test2, "last_msg"))

    def test_multiservice_pubsub(self):
        node1 = DseNode(self.messaging_config, "testnode1", [])
        test1 = FakeDataSource('test1')
        test2 = FakeDataSource('test2')
        node1.register_service(test1)
        node1.register_service(test2)
        node2 = DseNode(self.messaging_config, "testnode2", [])
        test3 = FakeDataSource('test3')
        node2.register_service(test3)

        test1.subscribe('test3', 'p')
        helper.retry_check_function_return_value(
            lambda: hasattr(test1, 'last_msg'), True)
        test3.publish('p', 42)
        helper.retry_check_function_return_value(
            lambda: test1.last_msg['data'], 42)
        self.assertFalse(hasattr(test2, "last_msg"))
        self.assertFalse(hasattr(test3, "last_msg"))

    def test_subscribe_snapshot(self):
        node = DseNode(self.messaging_config, "test", [])
        test1 = FakeDataSource('test1')
        test2 = FakeDataSource('test2')
        node.register_service(test1)
        node.register_service(test2)

        test1.subscribe('test2', 'fake_table')
        helper.retry_check_function_return_value(
            lambda: hasattr(test1, 'last_msg'), True)
        self.assertEqual(test1.last_msg['data'], test2.state['fake_table'])

    def test_datasource_sub(self):
        node = DseNode(self.messaging_config, "testnode", [])
        nova_client = mock.MagicMock()
        with mock.patch.object(novaclient.client.Client, '__init__',
                               return_value=nova_client):
            nova = NovaDriver(
                name='nova', args=helper.datasource_openstack_args())
            test = FakeDataSource('test')
            node.register_service(nova)
            node.register_service(test)

            nova.subscribe('test', 'p')
            helper.retry_check_function_return_value(
                lambda: hasattr(nova, 'last_msg'), True)
            test.publish('p', 42)
            helper.retry_check_function_return_value(
                lambda: nova.last_msg['data'], 42)
            self.assertFalse(hasattr(test, "last_msg"))

    def test_datasource_unsub(self):
        node = DseNode(self.messaging_config, "testnode", [])
        nova_client = mock.MagicMock()
        with mock.patch.object(novaclient.client.Client, '__init__',
                               return_value=nova_client):
            nova = NovaDriver(
                name='nova', args=helper.datasource_openstack_args())
            test = FakeDataSource('test')
            node.register_service(nova)
            node.register_service(test)

            nova.subscribe('test', 'p')
            helper.retry_check_function_return_value(
                lambda: hasattr(nova, 'last_msg'), True)
            test.publish('p', 42)
            helper.retry_check_function_return_value(
                lambda: nova.last_msg['data'], 42)
            self.assertFalse(hasattr(test, "last_msg"))
            nova.unsubscribe('test', 'p')
            test.publish('p', 43)
            # hard to test that the message is never delivered
            time.sleep(0.2)
            self.assertEqual(nova.last_msg['data'], 42)

    def test_datasource_pub(self):
        node = DseNode(self.messaging_config, "testnode", [])
        nova_client = mock.MagicMock()
        with mock.patch.object(novaclient.client.Client, '__init__',
                               return_value=nova_client):
            nova = NovaDriver(
                name='nova', args=helper.datasource_openstack_args())
            test = FakeDataSource('test')
            node.register_service(nova)
            node.register_service(test)

            test.subscribe('nova', 'p')
            helper.retry_check_function_return_value(
                lambda: hasattr(test, 'last_msg'), True)
            nova.publish('p', 42)
            helper.retry_check_function_return_value(
                lambda: test.last_msg['data'], 42)
            self.assertFalse(hasattr(nova, "last_msg"))

    def test_datasource_poll(self):
        node = DseNode(self.messaging_config, "testnode", [])
        pub = FakeDataSource('pub')
        sub = FakeDataSource('sub')
        node.register_service(pub)
        node.register_service(sub)

        sub.subscribe('pub', 'fake_table')
        pub.state = {'fake_table': set([(1, 2)])}
        pub.poll()
        helper.retry_check_function_return_value(
            lambda: sub.last_msg['data'], set(pub.state['fake_table']))
        self.assertFalse(hasattr(pub, "last_msg"))

    def test_policy(self):
        node = DseNode(self.messaging_config, "testnode", [])
        data = FakeDataSource('data')
        engine = Dse2Runtime('engine')
        node.register_service(data)
        node.register_service(engine)

        engine.create_policy('alpha')
        engine.create_policy('data')
        self.insert_rule(engine, 'p(x) :- data:fake_table(x)', 'alpha')
        data.state = {'fake_table': set([(1,), (2,)])}
        data.poll()
        helper.retry_check_db_equal(
            engine, 'p(x)', 'p(1) p(2)', target='alpha')
        self.assertFalse(hasattr(engine, "last_msg"))

    def insert_rule(self, engine, statement, target=None):
        statement = compile.parse1(statement)
        if target is None:
            e = compile.Event(statement)
        else:
            e = compile.Event(statement, target=target)
        engine.process_policy_update([e])

    # TODO(dse2): enable once tests are isolated from each other
    # def test_unregister(self):
    #     node = DseNode(self.messaging_config, "test", [])
    #     test1 = FakeDataSource('test1')
    #     node.register_service(test1)
    #     node.unregister_service('test1')
    #     self.assertRaises(congressException.NotFound,
    #                       node.invoke_service_rpc,
    #                       'test1', 'get_status')
