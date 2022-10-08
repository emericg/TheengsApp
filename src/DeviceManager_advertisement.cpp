/*
    Theengs - Decode things and devices
    Copyright: (c) Florian ROBERT

    This file is part of Theengs.

    Theengs is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    Theengs is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include "DeviceManager.h"
#include "SettingsManager.h"
#include "MqttManager.h"

#include "utils_bits.h"

#include <decoder.h> // Theengs decoder
#include "device_theengs.h"

#include <QBluetoothDeviceInfo>
#include <QList>
#include <QDebug>

/* ************************************************************************** */

void DeviceManager::updateBleDevice_simple(const QBluetoothDeviceInfo &info)
{
    updateBleDevice(info, QBluetoothDeviceInfo::Field::None);
}

void DeviceManager::updateBleDevice(const QBluetoothDeviceInfo &info,
                                    QBluetoothDeviceInfo::Fields updatedFields)
{
    //qDebug() << "updateBleDevice() " << info.name() << info.address(); // << info.deviceUuid() // << " updatedFields: " << updatedFields
    bool status = false;

    // We don't use QBluetoothDeviceInfo::Fields, it's unreliable
    Q_UNUSED(updatedFields)

    //if (info.name().isEmpty()) return; // skip beacons
    if (info.name().replace('-', ':') == info.address().toString()) return; // skip beacons

    for (auto d: qAsConst(m_devices_model->m_devices)) // KNOWN DEVICES ////////
    {
        Device *dd = qobject_cast<Device*>(d);

#if defined(Q_OS_MACOS) || defined(Q_OS_IOS)
        if (dd && dd->getAddress() == info.deviceUuid().toString())
#else
        if (dd && dd->getAddress() == info.address().toString())
#endif
        {
            dd->setName(info.name());
            dd->setRssi(info.rssi());

            QString mac_qstr = dd->getAddressMAC();
            mac_qstr.remove(':');
            std::string mac_str = mac_qstr.toStdString();

            const QList<quint16> &manufacturerIds = info.manufacturerIds();
            for (const auto id: manufacturerIds)
            {
                //qDebug() << info.name() << info.address() << Qt::hex
                //         << "ID" << id
                //         << "manufacturer data" << Qt::dec << info.manufacturerData(id).count() << Qt::hex
                //         << "bytes:" << info.manufacturerData(id).toHex();

                dd->parseAdvertisementData(DeviceUtils::BLE_ADV_MANUFACTURERDATA,
                                           id, info.manufacturerData(id));

                DynamicJsonDocument doc(2048);
                doc["id"] = mac_str;
                doc["name"] = info.name().toStdString();
                doc["manufacturerdata"] = QByteArray::number(endian_flip_16(id), 16).rightJustified(4, '0').toStdString() + info.manufacturerData(id).toHex().toStdString();
                doc["rssi"] = info.rssi();

                TheengsDecoder a;
                JsonObject obj = doc.as<JsonObject>();

                if (a.decodeBLEJson(obj) >= 0)
                {
                    obj.remove("manufacturerdata");

                    std::string output;
                    serializeJson(obj, output);
                    //qDebug() << "output:" << output.c_str();

                    DeviceTheengs *ddd = dynamic_cast<DeviceTheengs*>(dd);
                    if (ddd) ddd->parseTheengsAdvertisement(QString::fromStdString(output));

                    SettingsManager *sm = SettingsManager::getInstance();
                    MqttManager *mq = MqttManager::getInstance();
                    if (sm && mq && !mac_str.empty())
                    {
                        QString topic = sm->getMqttTopicA() + "/" + sm->getMqttTopicB() + "/BTtoMQTT/" + mac_qstr;

                        status = mq->publish(topic, QString::fromStdString(output));
                    }

                    status = true;
                }
                else
                {
                    //std::string input;
                    //serializeJson(doc, input);
                    //qDebug() << "input :" << input.c_str();
                }
            }

            const QList<QBluetoothUuid> &serviceIds = info.serviceIds();
            for (const auto id: serviceIds)
            {
                //qDebug() << info.name() << info.address() << Qt::hex
                //         << "ID" << id
                //         << "service data" << Qt::dec << info.serviceData(id).count() << Qt::hex
                //         << "bytes:" << info.serviceData(id).toHex();

                dd->parseAdvertisementData(DeviceUtils::BLE_ADV_MANUFACTURERDATA,
                                           id.toUInt16(), info.serviceData(id));

                DynamicJsonDocument doc(2048);
                doc["id"] = mac_str;
                doc["name"] = info.name().toStdString();
                doc["servicedata"] = info.serviceData(id).toHex().toStdString();
                doc["servicedatauuid"] = QByteArray::number(id.toUInt16(), 16).rightJustified(4, '0').toStdString();
                doc["rssi"] = info.rssi();

                JsonObject obj = doc.as<JsonObject>();

                TheengsDecoder dec;
                if (dec.decodeBLEJson(obj) >= 0)
                {
                    obj.remove("servicedata");
                    obj.remove("servicedatauuid");

                    std::string output;
                    serializeJson(obj, output);
                    //qDebug() << "output:" << output.c_str();

                    DeviceTheengs *ddd = dynamic_cast<DeviceTheengs*>(dd);
                    if (ddd) ddd->parseTheengsAdvertisement(QString::fromStdString(output));

                    SettingsManager *sm = SettingsManager::getInstance();
                    MqttManager *mq = MqttManager::getInstance();
                    if (sm && mq)
                    {
                        QString topic = sm->getMqttTopicA() + "/" + sm->getMqttTopicB() + "/BTtoMQTT/" + mac_qstr;

                        status = mq->publish(topic, QString::fromStdString(output));
                    }

                    status = true;
                }
                else
                {
                    //std::string input;
                    //serializeJson(doc, input);
                    //qDebug() << "input :" << input.c_str();
                }
            }

            // Dynamic updates
            if (m_listening)
            {
                if (!dd->isEnabled()) return;
                if (!dd->hasBluetoothConnection()) return;
                if (dd->getName() == "ThermoBeacon") return;

                //qDebug() << "adding from updateBleDevice()";
                //qDebug() << "last upd" << dd->getLastUpdateInt() << dd->needsUpdateRt();
                //qDebug() << "last err" << dd->getLastErrorInt() << dd->isErrored();

                // old or no data: go for refresh
                // also, check if we didn't already fail to update in the last couple minutes
                if (dd->needsUpdateRt() && !dd->isErrored())
                {
                    if (!m_devices_updating_queue.contains(dd) && !m_devices_updating.contains(dd))
                    {
                        m_devices_updating_queue.push_back(dd);
                        dd->refreshQueued();
                        refreshDevices_continue();
                    }
                }
            }

            break;
        }
    }

    // No need to try to handle unknown devices on macOS / iOS, because
    // we don't have MAC addresses to ID them...
    // Maybe later if Theengs decoder can output MAC from advertisement packets
#if defined(Q_OS_MACOS) || defined(Q_OS_IOS)
    bool appleOS = true;
#else
    bool appleOS = false;
#endif

    if (!status && !appleOS) // UN-KNOWN DEVICES ///////////////////////////////////////////
    {
        QString mac_qstr = info.address().toString();
        QString mac_qstr_clean = mac_qstr;
        std::string mac_str = mac_qstr.toStdString();

        const QList<quint16> &manufacturerIds = info.manufacturerIds();
        for (const auto id: manufacturerIds)
        {
            //qDebug() << info.name() << info.address() << Qt::hex
            //         << "ID" << id
            //         << "manufacturer data" << Qt::dec << info.manufacturerData(id).count() << Qt::hex
            //         << "bytes:" << info.manufacturerData(id).toHex();

            DynamicJsonDocument doc(2048);
            doc["id"] = mac_str;
            doc["name"] = info.name().toStdString();
            doc["manufacturerdata"] = QByteArray::number(endian_flip_16(id), 16).rightJustified(4, '0').toStdString() + info.manufacturerData(id).toHex().toStdString();
            doc["rssi"] = info.rssi();

            TheengsDecoder dec;
            JsonObject obj = doc.as<JsonObject>();

            if (dec.decodeBLEJson(obj) >= 0)
            {
                obj.remove("manufacturerdata");

                std::string output;
                serializeJson(obj, output);
                //qDebug() << "(UNKNOWN DEVICE) output (mfd) " << output.c_str();

                SettingsManager *sm = SettingsManager::getInstance();
                MqttManager *mq = MqttManager::getInstance();
                if (sm && mq)
                {
                    QString topic = sm->getMqttTopicA() + "/" + sm->getMqttTopicB() + "/BTtoMQTT/" + mac_qstr_clean;

                    status = mq->publish(topic, QString::fromStdString(output));
                }

                status = true;
            }
        }

        const QList<QBluetoothUuid> &serviceIds = info.serviceIds();
        for (const auto id: serviceIds)
        {
            //qDebug() << info.name() << info.address() << Qt::hex
            //         << "ID" << id
            //         << "service data" << Qt::dec << info.serviceData(id).count() << Qt::hex
            //         << "bytes:" << info.serviceData(id).toHex();

            DynamicJsonDocument doc(2048);
            doc["id"] = mac_str;
            doc["name"] = info.name().toStdString();
            doc["servicedata"] = info.serviceData(id).toHex().toStdString();
            doc["servicedatauuid"] = QByteArray::number(id.toUInt16(), 16).rightJustified(4, '0').toStdString();
            doc["rssi"] = info.rssi();

            TheengsDecoder dec;
            JsonObject obj = doc.as<JsonObject>();

            if (dec.decodeBLEJson(obj) >= 0)
            {
                obj.remove("servicedata");
                obj.remove("servicedatauuid");

                std::string output;
                serializeJson(obj, output);
                //qDebug() << "(UNKNOWN DEVICE) output (svd)" << output.c_str();

                SettingsManager *sm = SettingsManager::getInstance();
                MqttManager *mq = MqttManager::getInstance();
                if (sm && mq)
                {
                    QString topic = sm->getMqttTopicA() + "/" + sm->getMqttTopicB() + "/BTtoMQTT/" + mac_qstr_clean;

                    status = mq->publish(topic, QString::fromStdString(output));
                }

                status = true;
            }
        }
    }

    if (m_scanning) // Dynamic scanning ////////////////////////////////////////
    {
        //qDebug() << "addBleDevice(" << info.name() << ") FROM DYNAMIC SCANNING";
        addBleDevice(info);
    }
}

/* ************************************************************************** */
