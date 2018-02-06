# -*- coding: utf-8 -*-
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.slack_data_to_zulip_data import (
    get_model_id,
    build_zerver_realm,
    get_user_email,
    get_user_avatar_source,
    get_user_timezone,
    users_to_zerver_userprofile,
    build_defaultstream,
    build_pm_recipient_sub_from_user,
    build_subscription,
    channels_to_zerver_stream,
    slack_workspace_to_realm,
    get_total_messages_and_usermessages,
    get_message_sending_user,
    build_zerver_usermessage,
    channel_message_to_zerver_message,
    convert_slack_workspace_messages,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import (
    Realm,
)
from zerver.lib.test_runner import slow
from zerver.lib import mdiff
import ujson
import json

import os
from mock import mock, patch
from typing import Any, AnyStr, Dict, List, Optional, Set, Tuple, Text

class MuteFunction():
    # A mock class to temporarily suppress output to stdout
    def write(self, s):
        pass

class SlackImporter(ZulipTestCase):

    @slow('Does id allocation for to be imported objects and resets sequence id')
    def test_get_model_id(self) -> None:
        start_id_sequence = get_model_id(Realm, 'zerver_realm', 1)
        test_id_sequence = Realm.objects.all().last().id + 1

        self.assertEqual(start_id_sequence, test_id_sequence)

    def test_build_zerver_realm(self) -> None:
        fixtures_path = os.path.dirname(os.path.abspath(__file__)) + '/../fixtures/'
        realm_id = 2
        realm_subdomain = "test-realm"
        time = float(timezone_now().timestamp())
        test_realm = build_zerver_realm(fixtures_path, realm_id, realm_subdomain, time)
        test_zerver_realm_dict = test_realm[0]

        self.assertEqual(test_zerver_realm_dict['id'], realm_id)
        self.assertEqual(test_zerver_realm_dict['string_id'], realm_subdomain)
        self.assertEqual(test_zerver_realm_dict['name'], realm_subdomain)
        self.assertEqual(test_zerver_realm_dict['date_created'], time)

    def test_get_avatar_source(self) -> None:
        gravatar_image_url = "https:\/\/secure.gravatar.com\/avatar\/78dc7b2e1bf423df8c82fb2a62c8917d.jpg?s=24&d=https%3A%2F%2Fa.slack-edge.com%2F66f9%2Fimg%2Favatars%2Fava_0016-24.png"
        uploaded_avatar_url = "https:\/\/avatars.slack-edge.com\/2015-06-12\/6314338625_3c7c62301a2d61b4a756_24.jpg"
        self.assertEqual(get_user_avatar_source(gravatar_image_url), 'G')
        self.assertEqual(get_user_avatar_source(uploaded_avatar_url), 'U')

    def test_get_timezone(self) -> None:
        user_chicago_timezone = {"tz": "America\/Chicago"}
        user_timezone_none = {"tz": None}
        user_no_timezone = {}  # type: Dict[str, Any]

        self.assertEqual(get_user_timezone(user_chicago_timezone), "America\/Chicago")
        self.assertEqual(get_user_timezone(user_timezone_none), "America/New_York")
        self.assertEqual(get_user_timezone(user_no_timezone), "America/New_York")

    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_model_id", return_value=1)
    def test_users_to_zerver_userprofile(self, mock_get_model_id: mock.Mock,
                                         mock_get_data_file: mock.Mock) -> None:
        user_data = [{"id": "U0CBK5KAT",
                      "is_admin": True,
                      "is_bot": False,
                      "is_owner": True,
                      'name': 'Jane',
                      "real_name": "Jane Doe",
                      "deleted": False,
                      "profile": {"image_32": "https:\/\/secure.gravatar.com\/avatar\/random.png",
                                  "email": "jane@foo.com"}},
                     {"id": "U08RGD1RD",
                      "name": "john",
                      "deleted": False,
                      "real_name": "John Doe",
                      "profile": {"image_32": "", "email": "jon@gmail.com"}},
                     {"id": "U09TYF5Sk",
                      "name": "Bot",
                      "real_name": "Bot",
                      "is_bot": True,
                      "deleted": False,
                      "profile": {"image_32": "https:\/\/secure.gravatar.com\/avatar\/random1.png",
                                  "email": "bot1@zulipchat.com"}}]
        mock_get_data_file.return_value = user_data
        test_added_users = {'U08RGD1RD': 2,
                            'U0CBK5KAT': 1,
                            'U09TYF5Sk': 3}
        slack_data_dir = './random_path'
        timestamp = int(timezone_now().timestamp())
        with patch('sys.stdout', new=MuteFunction()):
            zerver_userprofile, added_users = users_to_zerver_userprofile(slack_data_dir, 1,
                                                                          timestamp, 'test_domain')

        self.assertDictEqual(added_users, test_added_users)

        self.assertEqual(zerver_userprofile[0]['id'], test_added_users['U0CBK5KAT'])
        self.assertEqual(len(zerver_userprofile), 3)
        self.assertEqual(zerver_userprofile[0]['id'], 1)
        self.assertEqual(zerver_userprofile[0]['is_realm_admin'], True)
        self.assertEqual(zerver_userprofile[0]['is_active'], True)
        self.assertEqual(zerver_userprofile[1]['is_staff'], False)
        self.assertEqual(zerver_userprofile[1]['is_bot'], False)
        self.assertEqual(zerver_userprofile[1]['enable_desktop_notifications'], True)
        self.assertEqual(zerver_userprofile[2]['bot_type'], 1)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_model_id", return_value=1)
    def test_build_defaultstream(self, mock_get_model_id: mock.Mock) -> None:
        realm_id = 1
        stream_id = 1
        default_channel_general = build_defaultstream('general', realm_id, stream_id, 1)
        test_default_channel = {'stream': 1, 'realm': 1, 'id': 1}
        self.assertDictEqual(test_default_channel, default_channel_general)
        default_channel_general = build_defaultstream('random', realm_id, stream_id, 1)
        test_default_channel = {'stream': 1, 'realm': 1, 'id': 1}
        self.assertDictEqual(test_default_channel, default_channel_general)
        self.assertIsNone(build_defaultstream('randd', 1, 1, 1))

    def test_build_pm_recipient_sub_from_user(self) -> None:
        zulip_user_id = 3
        recipient_id = 5
        subscription_id = 7
        recipient, sub = build_pm_recipient_sub_from_user(zulip_user_id, recipient_id, subscription_id)

        self.assertEqual(recipient['id'], sub['recipient'])
        self.assertEqual(recipient['type_id'], sub['user_profile'])

        self.assertEqual(recipient['type'], 1)
        self.assertEqual(recipient['type_id'], 3)

        self.assertEqual(sub['recipient'], 5)
        self.assertEqual(sub['id'], 7)
        self.assertEqual(sub['active'], True)

    def test_build_subscription(self) -> None:
        channel_members = ["U061A1R2R", "U061A3E0G", "U061A5N1G", "U064KUGRJ"]
        added_users = {"U061A1R2R": 1, "U061A3E0G": 8, "U061A5N1G": 7, "U064KUGRJ": 5}
        subscription_id = 7
        recipient_id = 12
        zerver_subscription = []  # type: List[Dict[str, Any]]
        zerver_subscription, final_subscription_id = build_subscription(channel_members,
                                                                        zerver_subscription,
                                                                        recipient_id,
                                                                        added_users,
                                                                        subscription_id)
        self.assertEqual(final_subscription_id, 7 + len(channel_members))
        # sanity checks
        self.assertEqual(zerver_subscription[0]['recipient'], 12)
        self.assertEqual(zerver_subscription[0]['id'], 7)
        self.assertEqual(zerver_subscription[0]['user_profile'], added_users[channel_members[0]])
        self.assertEqual(zerver_subscription[2]['user_profile'], added_users[channel_members[2]])
        self.assertEqual(zerver_subscription[3]['id'], 10)
        self.assertEqual(zerver_subscription[1]['recipient'],
                         zerver_subscription[3]['recipient'])
        self.assertEqual(zerver_subscription[1]['pin_to_top'], False)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_model_id", return_value=1)
    def test_channels_to_zerver_stream(self, mock_get_model_id: mock.Mock,
                                       mock_get_data_file: mock.Mock) -> None:

        added_users = {"U061A1R2R": 1, "U061A3E0G": 8, "U061A5N1G": 7, "U064KUGRJ": 5}
        zerver_userprofile = [{'id': 1}, {'id': 8}, {'id': 7}, {'id': 5}]
        realm_id = 3

        channel_data = [{'id': "C061A0WJG", 'name': 'random', 'created': '1433558319',
                         'is_general': False, 'members': ['U061A1R2R', 'U061A5N1G'],
                         'is_archived': True, 'topic': {'value': 'random'},
                         'purpose': {'value': 'no purpose'}},
                        {'id': "C061A0YJG", 'name': 'general1', 'created': '1433559319',
                         'is_general': False, 'is_archived': False,
                         'members': ['U061A1R2R', 'U061A5N1G', 'U064KUGRJ'],
                         'topic': {'value': 'general channel'}, 'purpose': {'value': 'For everyone'}},
                        {'id': "C061A0HJG", 'name': 'feedback', 'created': '1433558359',
                         'is_general': False, 'members': ['U061A3E0G'], 'is_archived': False,
                         'topic': {'value': ''}, 'purpose': {'value': ''}}]
        mock_get_data_file.return_value = channel_data

        with patch('sys.stdout', new=MuteFunction()):
            channel_to_zerver_stream_output = channels_to_zerver_stream('./random_path', realm_id,
                                                                        added_users, zerver_userprofile)
        zerver_defaultstream = channel_to_zerver_stream_output[0]
        zerver_stream = channel_to_zerver_stream_output[1]
        added_channels = channel_to_zerver_stream_output[2]
        zerver_subscription = channel_to_zerver_stream_output[3]
        zerver_recipient = channel_to_zerver_stream_output[4]
        added_recipient = channel_to_zerver_stream_output[5]

        test_added_channels = {'random': 1, 'general1': 2, 'feedback': 3}
        test_added_recipient = {'random': 1, 'general1': 2, 'feedback': 3}

        # zerver defaultstream already tested in helper functions
        self.assertEqual(zerver_defaultstream, [{'id': 1, 'realm': 3, 'stream': 1}])

        self.assertDictEqual(test_added_channels, added_channels)
        self.assertDictEqual(test_added_recipient, added_recipient)

        # functioning of zerver subscriptions are already tested in the helper functions
        # This is to check the concatenation of the output lists from the helper functions
        # subscriptions for stream
        self.assertEqual(zerver_subscription[3]['recipient'], 2)
        self.assertEqual(zerver_subscription[5]['recipient'], 3)
        # subscription for users
        self.assertEqual(zerver_subscription[6]['recipient'], 4)
        self.assertEqual(zerver_subscription[7]['user_profile'], 8)

        # recipients for stream
        self.assertEqual(zerver_recipient[1]['id'], zerver_subscription[3]['recipient'])
        self.assertEqual(zerver_recipient[2]['type_id'], zerver_stream[2]['id'])
        self.assertEqual(zerver_recipient[0]['type'], 2)
        # recipients for users (already tested in helped function)
        self.assertEqual(zerver_recipient[3]['type'], 1)

        # stream mapping
        self.assertEqual(zerver_stream[0]['name'], channel_data[0]['name'])
        self.assertEqual(zerver_stream[0]['deactivated'], channel_data[0]['is_archived'])
        self.assertEqual(zerver_stream[0]['description'],
                         "topic: {}\npurpose: {}".format('random', 'no purpose'))
        self.assertEqual(zerver_stream[0]['invite_only'], not channel_data[0]["is_general"])
        self.assertEqual(zerver_stream[0]['realm'], realm_id)
        self.assertEqual(zerver_stream[2]['id'],
                         test_added_channels[zerver_stream[2]['name']])

    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_zerver_realm", return_value=[{}])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.users_to_zerver_userprofile",
                return_value=[[], {}])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.channels_to_zerver_stream",
                return_value=[[], [], {}, [], [], {}])
    def test_slack_workspace_to_realm(self, mock_channels_to_zerver_stream: mock.Mock,
                                      mock_users_to_zerver_userprofile: mock.Mock,
                                      mock_build_zerver_realm: mock.Mock) -> None:

        realm_id = 1
        realm, added_users, added_recipient, added_channels = slack_workspace_to_realm(realm_id,
                                                                                       'test-realm',
                                                                                       './fixture',
                                                                                       './random_path')
        test_zerver_realmdomain = [{'realm': realm_id, 'allow_subdomains': False,
                                    'domain': 'zulipchat.com', 'id': realm_id}]
        # Functioning already tests in helper functions
        self.assertEqual(added_users, {})
        self.assertEqual(added_channels, {})
        self.assertEqual(added_recipient, {})

        zerver_realmdomain = realm['zerver_realmdomain']
        self.assertListEqual(zerver_realmdomain, test_zerver_realmdomain)
        self.assertEqual(realm['zerver_userpresence'], [])
        self.assertEqual(realm['zerver_stream'], [])
        self.assertEqual(realm['zerver_userprofile'], [])
        self.assertEqual(realm['zerver_realm'], [{}])

    @mock.patch("os.listdir", return_value = ['2015-08-08.json', '2016-01-15.json'])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    def test_get_total_messages_and_usermessages(self, mock_get_data_file: mock.Mock,
                                                 mock_list_dir: mock.Mock) -> None:

        date1 = [{"text": "<@U8VAHEVUY> has joined the channel", "subtype": "channel_join"},
                 {"text": "message"},
                 {"text": "random"},
                 {"text": "test messsage"}]
        date2 = [{"text": "test message 2", "subtype": "channel_leave"},
                 {"text": "random test"},
                 {"text": "message", "subtype": "channel_name"}]
        mock_get_data_file.side_effect = [date1, date2]

        added_recipient = {'random': 2}
        zerver_subscription = [{'recipient': 2}, {'recipient': 4}, {'recipient': 2}]

        total_messages, total_usermessages = get_total_messages_and_usermessages('./path',
                                                                                 'random',
                                                                                 zerver_subscription,
                                                                                 added_recipient)
        # subtype: channel_join, channel_leave are filtered out
        self.assertEqual(total_messages, 4)
        self.assertEqual(total_usermessages, 8)

    def test_get_message_sending_user(self) -> None:
        message_with_file = {'subtype': 'file', 'type': 'message',
                             'file': {'user': 'U064KUGRJ'}}
        message_without_file = {'subtype': 'file', 'type': 'messge', 'user': 'U064KUGRJ'}

        user_file = get_message_sending_user(message_with_file)
        self.assertEqual(user_file, 'U064KUGRJ')
        user_without_file = get_message_sending_user(message_without_file)
        self.assertEqual(user_without_file, 'U064KUGRJ')

    def test_build_zerver_message(self) -> None:
        zerver_usermessage = []  # type: List[Dict[str, Any]]
        usermessage_id = 6
        zerver_subscription = [{'recipient': 2, 'user_profile': 7},
                               {'recipient': 4, 'user_profile': 12},
                               {'recipient': 2, 'user_profile': 16},
                               {'recipient': 2, 'user_profile': 15},
                               {'recipient': 2, 'user_profile': 3}]
        recipient_id = 2
        mentioned_users_id = [12, 3, 16]
        message_id = 9

        test_zerver_usermessage, test_usermessage_id = build_zerver_usermessage(zerver_usermessage,
                                                                                usermessage_id,
                                                                                zerver_subscription,
                                                                                recipient_id,
                                                                                mentioned_users_id,
                                                                                message_id)
        self.assertEqual(test_usermessage_id, 10)

        self.assertEqual(test_zerver_usermessage[0]['flags_mask'], 1)
        self.assertEqual(test_zerver_usermessage[0]['message'], message_id)
        self.assertEqual(test_zerver_usermessage[1]['user_profile'],
                         zerver_subscription[2]['user_profile'])
        self.assertEqual(test_zerver_usermessage[1]['flags_mask'], 9)
        self.assertEqual(test_zerver_usermessage[3]['id'], 9)
        self.assertEqual(test_zerver_usermessage[3]['message'], message_id)

    @mock.patch("os.listdir", return_value = ['2015-08-08.json', '2016-01-15.json'])
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_data_file")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.build_zerver_usermessage", return_value = [[], 2])
    def test_channel_message_to_zerver_message(self, mock_build_zerver_usermessage: mock.Mock,
                                               mock_get_data_file: mock.Mock, mock_listdir: mock.Mock) -> None:

        user_data = [{"id": "U066MTL5U", "name": "john doe", "deleted": False, "real_name": "John"},
                     {"id": "U061A5N1G", "name": "jane doe", "deleted": False, "real_name": "Jane"},
                     {"id": "U061A1R2R", "name": "jon", "deleted": False, "real_name": "Jon"}]

        added_users = {"U066MTL5U": 5, "U061A5N1G": 24, "U061A1R2R": 43}

        date1 = [{"text": "<@U066MTL5U> has joined the channel", "subtype": "channel_join",
                  "user": "U066MTL5U", "ts": "1434139102.000002"},
                 {"text": "<@U061A5N1G>: hey!", "user": "U061A1R2R",
                  "ts": "1437868294.000006", "has_image": True},
                 {"text": "random", "user": "U061A5N1G",
                  "ts": "1439868294.000006"},
                 {"text": "<http://journals.plos.org/plosone/article>", "user": "U061A1R2R",
                  "ts": "1463868370.000008"}]  # type: List[Dict[str, Any]]

        date2 = [{"text": "test message 2", "user": "U061A5N1G",
                  "ts": "1433868549.000010"},
                 {"text": "random test", "user": "U061A1R2R",
                  "ts": "1433868669.000012"}]

        mock_get_data_file.side_effect = [user_data, date1, date2]
        added_recipient = {'random': 2}
        constants = ['./random_path', 2]
        ids = [3, 7]
        channel_name = 'random'

        zerver_usermessage = []  # type: List[Dict[str, Any]]
        zerver_subscription = []  # type: List[Dict[str, Any]]
        zerver_message, zerver_usermessage = channel_message_to_zerver_message(constants, channel_name,
                                                                               added_users, added_recipient,
                                                                               zerver_subscription, ids)
        # functioning already tested in helper function
        self.assertEqual(zerver_usermessage, [])
        # subtype: channel_join is filtered
        self.assertEqual(len(zerver_message), 5)

        # Message conversion already tested in tests.test_slack_message_conversion
        self.assertEqual(zerver_message[0]['content'], '@**Jane**: hey!')
        self.assertEqual(zerver_message[0]['has_link'], False)
        self.assertEqual(zerver_message[2]['content'], 'http://journals.plos.org/plosone/article')
        self.assertEqual(zerver_message[2]['has_link'], True)

        self.assertEqual(zerver_message[3]['subject'], 'from slack')
        self.assertEqual(zerver_message[4]['recipient'], added_recipient[channel_name])
        self.assertEqual(zerver_message[2]['subject'], 'from slack')
        self.assertEqual(zerver_message[1]['recipient'], added_recipient[channel_name])

        self.assertEqual(zerver_message[1]['id'], 4)
        self.assertEqual(zerver_message[4]['id'], 7)

        self.assertIsNone(zerver_message[3]['rendered_content'])
        self.assertEqual(zerver_message[0]['has_image'], date1[1]['has_image'])
        self.assertEqual(zerver_message[0]['pub_date'], float(date1[1]['ts']))
        self.assertEqual(zerver_message[2]['rendered_content_version'], 1)

        self.assertEqual(zerver_message[0]['sender'], 43)
        self.assertEqual(zerver_message[3]['sender'], 24)

    @mock.patch("zerver.lib.slack_data_to_zulip_data.channel_message_to_zerver_message")
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_model_id", return_value=1)
    @mock.patch("zerver.lib.slack_data_to_zulip_data.get_total_messages_and_usermessages", return_value=[1, 2])
    def test_convert_slack_workspace_messages(self, mock_get_total_messages_and_usermessages: mock.Mock,
                                              mock_get_model_id: mock.Mock, mock_message: mock.Mock) -> None:
        added_channels = {'random': 1, 'general': 2}

        zerver_message1 = [{'id': 1}]
        zerver_message2 = [{'id': 5}]

        realm = {'zerver_subscription': []}  # type: Dict[str, Any]

        zerver_usermessage1 = [{'id': 3}, {'id': 5}]
        zerver_usermessage2 = [{'id': 6}, {'id': 9}]

        mock_message.side_effect = [[zerver_message1, zerver_usermessage1],
                                    [zerver_message2, zerver_usermessage2]]
        with patch('sys.stdout', new=MuteFunction()):
            message_json = convert_slack_workspace_messages('./random_path', 2, {},
                                                            {}, added_channels,
                                                            realm)
        self.assertEqual(message_json['zerver_message'], zerver_message1 + zerver_message2)
        self.assertEqual(message_json['zerver_usermessage'], zerver_usermessage1 + zerver_usermessage2)
