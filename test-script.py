async def subscribe_to_server(adresses: str =  "opc.tcp://10.205.139.4:4840", username: str = "OPCGB", password: str = "OPCgb123!"):
    """
    Parameters
    ----------
    adresses - The address of the OPC UA server
    username - The username to use when connecting to the OPC UA server
    password - The password to use when connecting to the OPC UA server
    """

    subscribing_params = ua.CreateSubscriptionParameters()
    subscribing_params.RequestedPublishingInterval = 2000
    subscribing_params.RequestedLifetimeCount = 6000
    subscribing_params.RequestedMaxKeepAliveCount = 20
    subscribing_params.MaxNotificationsPerPublish = 100
    subscribing_params.PublishingEnabled = True
    subscribing_params.Priority = 0

    client:Client = None

    while True:
        try:
            if client is None:
                client = await connect_opcua(adresses, username, password)

            await client.check_connection()

            handler = SubHandler(adresses)
            sub = await client.create_subscription(subscribing_params, handler)
            logger_programming.info("Made a new subscription")
            alarmConditionType = client.get_node("ns=0;i=2915")
            server_node = client.get_node(ua.NodeId(Identifier=2253,
                                                    NodeIdType=ua.NodeIdType.Numeric, NamespaceIndex=0))

            await sub.subscribe_alarms_and_conditions(server_node,alarmConditionType)
            while True:
                await asyncio.sleep(0.1)
                await client.check_connection()

        except (ConnectionError, ua.UaError) as e:
            logger_programming.warning(f"{e} Reconnecting in 30 seconds")
            if client is not None:
                await client.delete_subscriptions(sub)
                await client.disconnect()
                client = None
            await asyncio.sleep(30)

        except Exception as e:
            logger_programming.error(f"Error connecting or subscribing to server {adresses}: {e}")
            if client is not None:
                await client.delete_subscriptions(sub)
                await client.disconnect()
            client = None
            await asyncio.sleep(30)


class SubHandler:
    """
    Handles the events received from the OPC UA server, and what to do with them.
    """

    def __init__(self, address: str):
        self.address = address

    def status_change_notification(self, status: ua.StatusChangeNotification):
        """
        Called when a status change notification is received from the server.
        """
        # Handle the status change event. This could be logging the change, raising an alert, etc.
        print(f"Status change received from subscription with status: {status}")
        logger_opcua_alarm.info(status)



    async def event_notification(self, event):
        """
        This function is called when an event is received from the OPC UA server.
        and saves it to a log file.
        returns: the event message
        """

        opcua_alarm_message = {
            "New event received from": self.address
        }

        attributes_to_check = [
            "Message", "Time", "Severity", "SuppressedOrShelved",
            "AckedState", "ConditionClassId", "NodeId", "Quality", "Retain",
            "ActiveState", "EnabledState"
        ]
![UA](https://github.com/FreeOpcUa/opcua-asyncio/assets/71367974/8eff51a8-84d0-4126-bed8-d66d959fc85a)
![TIAPortal](https://github.com/FreeOpcUa/opcua-asyncio/assets/71367974/4463bd68-5047-4a13-8b7e-fc074e18b8da)
