package com.kotmatetn.printagent

import android.app.PendingIntent
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.kotmatetn.printagent.printer.PrinterConfig
import com.kotmatetn.printagent.printer.PrinterConnectionManager
import com.kotmatetn.printagent.printer.PrinterRepository
import com.kotmatetn.printagent.printer.PrinterType
import com.kotmatetn.printagent.service.PrintAgentService

private const val ACTION_USB_PERMISSION = "com.kotmatetn.printagent.USB_PERMISSION"

class MainActivity : ComponentActivity() {

    private lateinit var repository: PrinterRepository
    private lateinit var usbManager: UsbManager
    private var testConnections: PrinterConnectionManager? = null

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { PrintAgentService.start(this) }

    private var pendingUsbCallback: ((UsbDevice) -> Unit)? = null
    private val usbPermissionReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.action != ACTION_USB_PERMISSION) return
            val device = if (Build.VERSION.SDK_INT >= 33) {
                intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableExtra(UsbManager.EXTRA_DEVICE)
            }
            val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
            if (granted && device != null) {
                pendingUsbCallback?.invoke(device)
            } else {
                Toast.makeText(this@MainActivity, "USB permission was refused", Toast.LENGTH_SHORT).show()
            }
            pendingUsbCallback = null
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as PrintAgentApplication
        repository = app.printerRepository
        usbManager = getSystemService(Context.USB_SERVICE) as UsbManager
        testConnections = PrinterConnectionManager(usbManager)

        val filter = IntentFilter(ACTION_USB_PERMISSION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(usbPermissionReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(usbPermissionReceiver, filter)
        }

        requestRuntimePermissionsAndStart()

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    PrinterAgentScreen(
                        repository = repository,
                        onRequestUsbPermission = ::requestUsbPermission,
                        onPairedBluetoothDevices = ::pairedBluetoothDevices,
                        onAttachedUsbDevices = { usbManager.deviceList.values.toList() },
                        onTestPrint = ::testPrint,
                    )
                }
            }
        }
    }

    override fun onDestroy() {
        runCatching { unregisterReceiver(usbPermissionReceiver) }
        testConnections?.closeAll()
        super.onDestroy()
    }

    private fun requestRuntimePermissionsAndStart() {
        val needed = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            needed += android.Manifest.permission.BLUETOOTH_CONNECT
            needed += android.Manifest.permission.BLUETOOTH_SCAN
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            needed += android.Manifest.permission.POST_NOTIFICATIONS
        }
        val missing = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            PrintAgentService.start(this)
        } else {
            permissionLauncher.launch(missing.toTypedArray())
        }
    }

    private fun pairedBluetoothDevices(): List<android.bluetooth.BluetoothDevice> {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
            ContextCompat.checkSelfPermission(this, android.Manifest.permission.BLUETOOTH_CONNECT)
            != PackageManager.PERMISSION_GRANTED
        ) {
            return emptyList()
        }
        val adapter = (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
            ?: return emptyList()
        return adapter.bondedDevices?.toList() ?: emptyList()
    }

    private fun requestUsbPermission(device: UsbDevice, onGranted: (UsbDevice) -> Unit) {
        if (usbManager.hasPermission(device)) {
            onGranted(device)
            return
        }
        pendingUsbCallback = onGranted
        val flags = if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0
        val pendingIntent = PendingIntent.getBroadcast(
            this, 0, Intent(ACTION_USB_PERMISSION).setPackage(packageName), flags,
        )
        usbManager.requestPermission(device, pendingIntent)
    }

    private fun testPrint(printer: PrinterConfig) {
        Thread {
            val text = "KOTMate Print Agent\nTest print OK\n\n\n\n"
            val bytes = text.toByteArray(Charsets.US_ASCII) + byteArrayOf(0x1D, 0x56, 0x00) // ESC/POS partial cut
            val result = runCatching { testConnections?.send(printer, bytes) }
            runOnUiThread {
                val message = if (result.isSuccess) "Test print sent to ${printer.name}" else {
                    "Test print failed: ${result.exceptionOrNull()?.message}"
                }
                Toast.makeText(this, message, Toast.LENGTH_LONG).show()
            }
        }.start()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PrinterAgentScreen(
    repository: PrinterRepository,
    onRequestUsbPermission: (UsbDevice, (UsbDevice) -> Unit) -> Unit,
    onPairedBluetoothDevices: () -> List<android.bluetooth.BluetoothDevice>,
    onAttachedUsbDevices: () -> List<UsbDevice>,
    onTestPrint: (PrinterConfig) -> Unit,
) {
    var showAddDialog by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<PrinterConfig?>(null) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("KOTMate Print Agent") }) },
        floatingActionButton = {
            FloatingActionButton(onClick = { showAddDialog = true }) { Text("+") }
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            Text(
                "Running on port ${repository.agentPort()} — register each printer below with " +
                    "the exact same name you give it in KOTMate's Settings → Printers " +
                    "(\"Windows Printer Name\" field, connection type \"Local Print Agent\").",
                modifier = Modifier.padding(16.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
            if (repository.printers.isEmpty()) {
                Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                    Text("No printers configured yet — tap + to add one.")
                }
            }
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(repository.printers, key = { it.id }) { printer ->
                    ListItem(
                        headlineContent = { Text(printer.name) },
                        supportingContent = { Text(printerSubtitle(printer)) },
                        trailingContent = {
                            Row {
                                TextButton(onClick = { onTestPrint(printer) }) { Text("Test") }
                                TextButton(onClick = { editing = printer }) { Text("Edit") }
                                TextButton(onClick = { repository.remove(printer.id) }) { Text("Delete") }
                            }
                        },
                    )
                    HorizontalDivider()
                }
            }
        }
    }

    if (showAddDialog || editing != null) {
        PrinterEditDialog(
            existing = editing,
            onDismiss = {
                showAddDialog = false
                editing = null
            },
            onSave = { config ->
                if (editing != null) repository.update(config) else repository.add(config)
                showAddDialog = false
                editing = null
            },
            onRequestUsbPermission = onRequestUsbPermission,
            onPairedBluetoothDevices = onPairedBluetoothDevices,
            onAttachedUsbDevices = onAttachedUsbDevices,
        )
    }
}

private fun printerSubtitle(printer: PrinterConfig): String = when (printer.type) {
    PrinterType.BLUETOOTH -> "Bluetooth · ${printer.bluetoothAddress}"
    PrinterType.USB -> "USB · vendor ${printer.usbVendorId}, product ${printer.usbProductId}"
    PrinterType.WIFI -> "WiFi · ${printer.wifiHost}:${printer.wifiPort}"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PrinterEditDialog(
    existing: PrinterConfig?,
    onDismiss: () -> Unit,
    onSave: (PrinterConfig) -> Unit,
    onRequestUsbPermission: (UsbDevice, (UsbDevice) -> Unit) -> Unit,
    onPairedBluetoothDevices: () -> List<android.bluetooth.BluetoothDevice>,
    onAttachedUsbDevices: () -> List<UsbDevice>,
) {
    var name by remember { mutableStateOf(existing?.name ?: "") }
    var type by remember { mutableStateOf(existing?.type ?: PrinterType.BLUETOOTH) }
    var bluetoothAddress by remember { mutableStateOf(existing?.bluetoothAddress) }
    var usbDevice by remember { mutableStateOf<UsbDevice?>(null) }
    var wifiHost by remember { mutableStateOf(existing?.wifiHost ?: "") }
    var wifiPort by remember { mutableStateOf((existing?.wifiPort ?: 9100).toString()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (existing == null) "Add printer" else "Edit printer") },
        text = {
            Column {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Printer name (must match Settings → Printers)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                Row {
                    PrinterType.entries.forEach { candidate ->
                        FilterChip(
                            selected = type == candidate,
                            onClick = { type = candidate },
                            label = { Text(candidate.name) },
                            modifier = Modifier.padding(end = 6.dp),
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                when (type) {
                    PrinterType.BLUETOOTH -> {
                        val devices = remember { onPairedBluetoothDevices() }
                        if (devices.isEmpty()) {
                            Text("No paired Bluetooth devices — pair the printer in Android's Bluetooth settings first.")
                        }
                        devices.forEach { device ->
                            @Suppress("MissingPermission")
                            val label = runCatching { device.name }.getOrNull() ?: device.address
                            FilterChip(
                                selected = bluetoothAddress == device.address,
                                onClick = { bluetoothAddress = device.address },
                                label = { Text("$label (${device.address})") },
                                modifier = Modifier.padding(vertical = 2.dp),
                            )
                        }
                    }
                    PrinterType.USB -> {
                        val devices = remember { onAttachedUsbDevices() }
                        if (devices.isEmpty()) {
                            Text("No USB devices attached — plug in the printer (with an OTG cable if needed).")
                        }
                        devices.forEach { device ->
                            FilterChip(
                                selected = usbDevice?.deviceId == device.deviceId,
                                onClick = {
                                    onRequestUsbPermission(device) { granted -> usbDevice = granted }
                                },
                                label = { Text(device.productName ?: device.deviceName) },
                                modifier = Modifier.padding(vertical = 2.dp),
                            )
                        }
                    }
                    PrinterType.WIFI -> {
                        OutlinedTextField(
                            value = wifiHost,
                            onValueChange = { wifiHost = it },
                            label = { Text("Printer IP address") },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(
                            value = wifiPort,
                            onValueChange = { wifiPort = it },
                            label = { Text("Port (usually 9100)") },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                enabled = name.isNotBlank() && when (type) {
                    PrinterType.BLUETOOTH -> bluetoothAddress != null
                    PrinterType.USB -> usbDevice != null || existing?.type == PrinterType.USB
                    PrinterType.WIFI -> wifiHost.isNotBlank()
                },
                onClick = {
                    val config = PrinterConfig(
                        id = existing?.id ?: java.util.UUID.randomUUID().toString(),
                        name = name.trim(),
                        type = type,
                        bluetoothAddress = if (type == PrinterType.BLUETOOTH) bluetoothAddress else null,
                        usbVendorId = if (type == PrinterType.USB) (usbDevice?.vendorId ?: existing?.usbVendorId) else null,
                        usbProductId = if (type == PrinterType.USB) (usbDevice?.productId ?: existing?.usbProductId) else null,
                        wifiHost = if (type == PrinterType.WIFI) wifiHost.trim() else null,
                        wifiPort = wifiPort.toIntOrNull() ?: 9100,
                    )
                    onSave(config)
                },
            ) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
