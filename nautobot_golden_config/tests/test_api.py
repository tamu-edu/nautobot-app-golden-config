"""Unit tests for nautobot_golden_config."""
from copy import deepcopy
from django.contrib.auth import get_user_model

from django.urls import reverse
from rest_framework import status

from nautobot.utilities.testing import APITestCase
from nautobot.extras.models import GitRepository
from nautobot_golden_config.models import GoldenConfigSetting

from .conftest import create_device, create_feature_rule_json, create_config_compliance, create_git_repos


User = get_user_model()


class GoldenConfigAPITest(APITestCase):  # pylint: disable=too-many-ancestors
    """Test the ConfigCompliance API."""

    def setUp(self):
        """Create a superuser and token for API calls."""
        super().setUp()
        self.device = create_device()
        self.compliance_rule_json = create_feature_rule_json(self.device)
        self.base_view = reverse("plugins-api:nautobot_golden_config-api:configcompliance-list")

    def test_root(self):
        """Validate the root for Nautobot Chatops API."""
        url = reverse("plugins-api:nautobot_golden_config-api:api-root")
        response = self.client.get(f"{url}?format=api", **self.header)
        self.assertEqual(response.status_code, 200)

    def test_device_list(self):
        """Verify that devices can be listed."""
        url = reverse("dcim-api:device-list")
        self.add_permissions("dcim.view_device")
        response = self.client.get(url, **self.header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_config_compliance_list_view(self):
        """Verify that config compliance objects can be listed."""
        actual = '{"foo": {"bar-1": "baz"}}'
        intended = '{"foo": {"bar-2": "baz"}}'
        create_config_compliance(
            self.device, actual=actual, intended=intended, compliance_rule=self.compliance_rule_json
        )
        self.add_permissions("nautobot_golden_config.view_configcompliance")
        response = self.client.get(self.base_view, **self.header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_config_compliance_post_new_json_compliant(self):
        """Verify that config compliance detail view."""
        self.add_permissions("nautobot_golden_config.add_configcompliance")
        response = self.client.post(
            self.base_view,
            data={
                "device": self.device.id,
                "intended": '{"foo": {"bar-1": "baz"}}',
                "actual": '{"foo": {"bar-1": "baz"}}',
                "rule": self.compliance_rule_json.id,
            },
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["compliance"])

    def test_config_compliance_post_new_json_not_compliant(self):
        """Verify that config compliance detail view."""
        self.add_permissions("nautobot_golden_config.add_configcompliance")
        response = self.client.post(
            self.base_view,
            data={
                "device": self.device.id,
                "intended": '{"foo": {"bar-1": "baz"}}',
                "actual": '{"foo": {"bar-2": "baz"}}',
                "rule": self.compliance_rule_json.id,
            },
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["compliance"])


class GoldenConfigSettingsAPITest(APITestCase):
    """Verify that the combination of values in a GoldenConfigSettings object POST are valid."""

    def setUp(self):
        """Create a superuser and token for API calls."""
        super().setUp()
        create_git_repos()
        self.add_permissions("nautobot_golden_config.add_goldenconfigsetting")
        self.add_permissions("nautobot_golden_config.change_goldenconfigsetting")
        self.base_view = reverse("plugins-api:nautobot_golden_config-api:goldenconfigsetting-list")
        self.data = {
            "tags": [],
            "computed_fields": {},
            "custom_fields": {},
            "_custom_field_data": {},
            "backup_match_rule": "backup-{{obj.site.region.parent.slug}}",
            "backup_path_template": "{{obj.site.region.slug}}/{{obj.site.slug}}/{{obj.name}}.cfg",
            "intended_match_rule": "intended-{{obj.site.region.parent.slug}}",
            "intended_path_template": "{{obj.site.region.slug}}/{{obj.site.slug}}/{{obj.name}}.cfg",
            "jinja_path_template": "templates/{{obj.platform.slug}}/{{obj.platform.slug}}_main.j2",
            "backup_test_connectivity": False,
            "scope": {"has_primary_ip": "True"},
            "sot_agg_query": "query ($device_id: ID!) {\r\n  device(id: $device_id) {\r\n    config_context\r\n    device_role {\r\n      name\r\n      slug\r\n    }\r\n    hostname: name\r\n    platform {\r\n      manufacturer {\r\n        name\r\n      }\r\n      name\r\n      napalm_driver\r\n      slug\r\n    }\r\n    primary_ip4 {\r\n      address\r\n      interface {\r\n        name\r\n      }\r\n      id\r\n    }\r\n    site {\r\n      name\r\n      region {\r\n        name\r\n        slug\r\n        parent {\r\n          name\r\n          slug\r\n        }\r\n      }\r\n      slug\r\n    }\r\n  }\r\n}",
            "jinja_repository": str(GitRepository.objects.get(name="test-jinja-repo-1").id),
            "backup_repository": [
                str(GitRepository.objects.get(name="test-backup-repo-1").id),
                str(GitRepository.objects.get(name="test-backup-repo-2").id),
            ],
            "intended_repository": [
                str(GitRepository.objects.get(name="test-intended-repo-1").id),
                str(GitRepository.objects.get(name="test-intended-repo-2").id),
            ],
        }
        # Since we enforce a singleton pattern on this model, nuke any auto-created objects.
        GoldenConfigSetting.objects.all().delete()

    def test_golden_config_settings_create_1backup_with_match_rule(self):
        """Verify that an invalid POST with an unnecessary match_rule returns an error."""
        bad_data = deepcopy(self.data)
        bad_data["backup_repository"] = [str(GitRepository.objects.get(name="test-backup-repo-1").id)]
        response = self.client.post(
            self.base_view,
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you configure only one backup repository, do not enter the backup repository matching rule template.",
        )
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_create_backup_match_rule_missing(self):
        """Verify that an invalid POST with a missing backup_match_rule returns an error."""
        bad_data = deepcopy(self.data)
        bad_data["backup_match_rule"] = ""
        response = self.client.post(
            self.base_view,
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you specify more than one backup repository, you must provide the backup repository matching rule template.",
        )
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_create_1intended_with_match_rule(self):
        """Verify that an invalid POST with an unnecessary match_rule returns an error."""
        bad_data = deepcopy(self.data)
        bad_data["intended_repository"] = [str(GitRepository.objects.get(name="test-intended-repo-2").id)]
        response = self.client.post(
            self.base_view,
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you configure only one intended repository, do not enter the intended repository matching rule template.",
        )
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_create_intended_match_rule_missing(self):
        """Verify that an invalid POST with a missing intended_match_rule returns an error."""
        bad_data = deepcopy(self.data)
        bad_data["intended_match_rule"] = ""
        response = self.client.post(
            self.base_view,
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you specify more than one intended repository, you must provide the intended repository matching rule template.",
        )
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_create_multiple_problems(self):
        """Verify that an invalid POST with multiple problems return multiple, correct errors."""
        bad_data = deepcopy(self.data)
        bad_data["backup_repository"] = [str(GitRepository.objects.get(name="test-backup-repo-1").id)]
        bad_data["intended_match_rule"] = ""
        response = self.client.post(
            self.base_view,
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you configure only one backup repository, do not enter the backup repository matching rule template.",
        )
        self.assertEqual(
            response.data["non_field_errors"][1],
            "If you specify more than one intended repository, you must provide the intended repository matching rule template.",
        )
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_create_good(self):
        """Test a POST with good values."""
        response = self.client.post(
            self.base_view,
            data=self.data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["created"])
        self.assertTrue(response.data["id"])
        self.assertEqual(response.data["backup_match_rule"], "backup-{{obj.site.region.parent.slug}}")
        self.assertEqual(
            response.data["backup_path_template"], "{{obj.site.region.slug}}/{{obj.site.slug}}/{{obj.name}}.cfg"
        )
        self.assertEqual(response.data["intended_match_rule"], "intended-{{obj.site.region.parent.slug}}")
        self.assertEqual(
            response.data["intended_path_template"], "{{obj.site.region.slug}}/{{obj.site.slug}}/{{obj.name}}.cfg"
        )
        self.assertEqual(
            response.data["jinja_path_template"], "templates/{{obj.platform.slug}}/{{obj.platform.slug}}_main.j2"
        )
        self.assertFalse(response.data["backup_test_connectivity"])
        self.assertEqual(response.data["scope"], {"has_primary_ip": "True"})
        self.assertEqual(
            response.data["sot_agg_query"],
            "query ($device_id: ID!) {\r\n  device(id: $device_id) {\r\n    config_context\r\n    device_role {\r\n      name\r\n      slug\r\n    }\r\n    hostname: name\r\n    platform {\r\n      manufacturer {\r\n        name\r\n      }\r\n      name\r\n      napalm_driver\r\n      slug\r\n    }\r\n    primary_ip4 {\r\n      address\r\n      interface {\r\n        name\r\n      }\r\n      id\r\n    }\r\n    site {\r\n      name\r\n      region {\r\n        name\r\n        slug\r\n        parent {\r\n          name\r\n          slug\r\n        }\r\n      }\r\n      slug\r\n    }\r\n  }\r\n}",
        )
        self.assertEqual(response.data["jinja_repository"], GitRepository.objects.get(name="test-jinja-repo-1").id)
        self.assertEqual(
            response.data["backup_repository"],
            [
                GitRepository.objects.get(name="test-backup-repo-1").id,
                GitRepository.objects.get(name="test-backup-repo-2").id,
            ],
        )
        self.assertEqual(
            response.data["intended_repository"],
            [
                GitRepository.objects.get(name="test-intended-repo-1").id,
                GitRepository.objects.get(name="test-intended-repo-2").id,
            ],
        )
        # Clean up
        GoldenConfigSetting.objects.all().delete()
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_update_good(self):
        """Verify a PUT to the valid settings object, with valid but changed values."""
        response_post = self.client.post(
            self.base_view,
            data=self.data,
            format="json",
            **self.header,
        )
        new_data = deepcopy(self.data)
        new_data["backup_repository"] = [str(GitRepository.objects.get(name="test-backup-repo-1").id)]
        new_data["backup_match_rule"] = ""
        response = self.client.put(
            f"{self.base_view}{response_post.data['id']}/",
            data=new_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["backup_match_rule"], "")
        self.assertEqual(
            response.data["backup_path_template"], "{{obj.site.region.slug}}/{{obj.site.slug}}/{{obj.name}}.cfg"
        )
        self.assertEqual(response.data["intended_match_rule"], "intended-{{obj.site.region.parent.slug}}")
        self.assertEqual(
            response.data["intended_path_template"], "{{obj.site.region.slug}}/{{obj.site.slug}}/{{obj.name}}.cfg"
        )
        self.assertEqual(
            response.data["jinja_path_template"], "templates/{{obj.platform.slug}}/{{obj.platform.slug}}_main.j2"
        )
        self.assertFalse(response.data["backup_test_connectivity"])
        self.assertEqual(response.data["scope"], {"has_primary_ip": "True"})
        self.assertEqual(
            response.data["sot_agg_query"],
            "query ($device_id: ID!) {\r\n  device(id: $device_id) {\r\n    config_context\r\n    device_role {\r\n      name\r\n      slug\r\n    }\r\n    hostname: name\r\n    platform {\r\n      manufacturer {\r\n        name\r\n      }\r\n      name\r\n      napalm_driver\r\n      slug\r\n    }\r\n    primary_ip4 {\r\n      address\r\n      interface {\r\n        name\r\n      }\r\n      id\r\n    }\r\n    site {\r\n      name\r\n      region {\r\n        name\r\n        slug\r\n        parent {\r\n          name\r\n          slug\r\n        }\r\n      }\r\n      slug\r\n    }\r\n  }\r\n}",
        )
        self.assertEqual(response.data["jinja_repository"], GitRepository.objects.get(name="test-jinja-repo-1").id)
        self.assertEqual(
            response.data["backup_repository"],
            [
                GitRepository.objects.get(name="test-backup-repo-1").id,
            ],
        )
        self.assertEqual(
            response.data["intended_repository"],
            [
                GitRepository.objects.get(name="test-intended-repo-1").id,
                GitRepository.objects.get(name="test-intended-repo-2").id,
            ],
        )
        # Clean up
        GoldenConfigSetting.objects.all().delete()
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_update_1backup_with_match_rule(self):
        """Verify a PUT to the valid settings object, with an invalid backup repo set, returns a 400."""
        response_post = self.client.post(
            self.base_view,
            data=self.data,
            format="json",
            **self.header,
        )
        bad_data = deepcopy(self.data)
        bad_data["backup_repository"] = [str(GitRepository.objects.get(name="test-backup-repo-1").id)]
        response = self.client.put(
            f"{self.base_view}{response_post.data['id']}/",
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you configure only one backup repository, do not enter the backup repository matching rule template.",
        )
        # Clean up
        GoldenConfigSetting.objects.all().delete()
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_update_backup_match_rule_missing(self):
        """Verify a PUT to the valid settings object, with an invalid backup repo set, returns a 400."""
        response_post = self.client.post(
            self.base_view,
            data=self.data,
            format="json",
            **self.header,
        )
        bad_data = deepcopy(self.data)
        bad_data["backup_match_rule"] = ""
        response = self.client.put(
            f"{self.base_view}{response_post.data['id']}/",
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you specify more than one backup repository, you must provide the backup repository matching rule template.",
        )
        # Clean up
        GoldenConfigSetting.objects.all().delete()
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_update_1intended_with_match_rule(self):
        """Verify a PUT to the valid settings object, with an invalid intended repo set, returns a 400."""
        response_post = self.client.post(
            self.base_view,
            data=self.data,
            format="json",
            **self.header,
        )
        bad_data = deepcopy(self.data)
        bad_data["intended_repository"] = [str(GitRepository.objects.get(name="test-intended-repo-1").id)]
        response = self.client.put(
            f"{self.base_view}{response_post.data['id']}/",
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you configure only one intended repository, do not enter the intended repository matching rule template.",
        )
        # Clean up
        GoldenConfigSetting.objects.all().delete()
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_golden_config_settings_update_intended_match_rule_missing(self):
        """Verify a PUT to the valid settings object, with an invalid intended repo set, returns a 400."""
        response_post = self.client.post(
            self.base_view,
            data=self.data,
            format="json",
            **self.header,
        )
        bad_data = deepcopy(self.data)
        bad_data["intended_match_rule"] = ""
        response = self.client.put(
            f"{self.base_view}{response_post.data['id']}/",
            data=bad_data,
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "If you specify more than one intended repository, you must provide the intended repository matching rule template.",
        )
        # Clean up
        GoldenConfigSetting.objects.all().delete()
        self.assertEqual(GoldenConfigSetting.objects.all().count(), 0)

    def test_settings_api_clean_up(self):
        """Transactional custom model, unable to use `get_or_create`.

        Delete all objects created of GitRepository type.
        """
        GitRepository.objects.all().delete()
        self.assertEqual(GitRepository.objects.all().count(), 0)

        # Put back a general GoldenConfigSetting object.
        global_settings = GoldenConfigSetting.objects.create()
        global_settings.save()
