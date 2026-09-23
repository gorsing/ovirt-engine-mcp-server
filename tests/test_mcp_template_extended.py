#!/usr/bin/env python3
"""Tests for TemplateExtendedMCP - 模板扩展模块测试."""
from types import SimpleNamespace


class TestTemplateExtendedGetTemplate:
    """get_template must read disks/nics through the service layer.

    ``Template`` / ``DiskAttachment`` entities expose no ``*_service()``
    methods in ovirtsdk4 4.6, so object-based access raises ``AttributeError``
    (which used to be swallowed, leaving every template with zero disks).
    SimpleNamespace here makes that constraint explicit.
    """

    @staticmethod
    def _template():
        return SimpleNamespace(
            id="tpl-1",
            name="base_os",
            description="base image",
            memory=4294967296,
            cpu=SimpleNamespace(
                topology=SimpleNamespace(cores=2, sockets=1, threads=1)
            ),
            os=SimpleNamespace(type="linux"),
            cluster=SimpleNamespace(name="Default", id="cluster-77"),
            status=SimpleNamespace(value="ok"),
            creation_time="2026-09-01 10:00:00",
            bios=SimpleNamespace(type=SimpleNamespace(value="seabios")),
        )

    @staticmethod
    def _attachment():
        return SimpleNamespace(
            disk=SimpleNamespace(id="disk-1"),
            bootable=True,
            interface=SimpleNamespace(value="virtio"),
        )

    @staticmethod
    def _nic():
        return SimpleNamespace(
            id="nic-1",
            name="nic1",
            mac=SimpleNamespace(address="56:6f:b4:e7:00:01"),
            interface=SimpleNamespace(value="virtio"),
            linked=True,
            vnic_profile=SimpleNamespace(name="ovirtmgmt"),
        )

    @staticmethod
    def _disk():
        return SimpleNamespace(
            id="disk-1",
            alias="base_os_disk1",
            provisioned_size=10737418240,
            actual_size=5368709120,
            storage_format=SimpleNamespace(value="qcow2"),
            storage_domain=None,  # live engines only fill storage_domains
            storage_domains=[SimpleNamespace(id="sd-9", name=None)],
        )

    @staticmethod
    def _mcp(attachments=(), nics=(), disk=None):
        from unittest.mock import MagicMock

        from ovirt_engine_mcp_server.mcp_template_extended import TemplateExtendedMCP

        mock_ovirt = MagicMock()
        mock_ovirt.connected = True
        system = mock_ovirt.connection.system_service.return_value

        template_service = system.templates_service.return_value.template_service.return_value
        template_service.get.return_value = TestTemplateExtendedGetTemplate._template()
        template_service.disk_attachments_service.return_value.list.return_value = list(attachments)
        template_service.nics_service.return_value.list.return_value = list(nics)
        system.templates_service.return_value.list.return_value = [
            TestTemplateExtendedGetTemplate._template()
        ]

        disk_holder = system.disks_service.return_value.disk_service.return_value
        disk_holder.get.return_value = disk

        sd = system.storage_domains_service.return_value.storage_domain_service.return_value.get.return_value
        sd.name = "hosted_storage"

        return TemplateExtendedMCP(mock_ovirt), template_service

    def test_get_template_reads_subcollections_through_services(self):
        mcp, template_service = self._mcp(
            attachments=[self._attachment()],
            nics=[self._nic()],
            disk=self._disk(),
        )

        result = mcp.get_template("base_os")

        assert result is not None
        assert result["name"] == "base_os"

        assert len(result["disks"]) == 1
        assert result["disks"][0]["name"] == "base_os_disk1"
        assert result["disks"][0]["size_gb"] == 10
        assert result["disks"][0]["format"] == "qcow2"
        assert result["disks"][0]["bootable"] is True
        assert result["disks"][0]["storage_domain"] == "hosted_storage"

        assert len(result["nics"]) == 1
        assert result["nics"][0]["name"] == "nic1"
        assert result["nics"][0]["vnic_profile"] == "ovirtmgmt"

        template_service.disk_attachments_service.assert_called_once()
        template_service.nics_service.assert_called_once()

    def test_list_template_disks_uses_service(self):
        mcp, template_service = self._mcp()

        assert mcp.list_template_disks("base_os") == []
        template_service.disk_attachments_service.assert_called_once()

    def test_list_template_nics_uses_service(self):
        mcp, template_service = self._mcp(nics=[self._nic()])

        result = mcp.list_template_nics("base_os")

        assert len(result) == 1
        assert result[0]["name"] == "nic1"
        template_service.nics_service.assert_called_once()

    def test_template_entity_has_no_service_methods(self):
        """Sanity: the caveat this module guards against is still real."""
        template = self._template()
        assert not hasattr(template, "disk_attachments_service")
        assert not hasattr(template, "nics_service")
        assert not hasattr(self._attachment(), "disk_service")
