package com.rooster.autonomous

import android.app.Activity
import android.graphics.Typeface
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var server: EditText
    private lateinit var token: EditText
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Rooster Autonomous Engineer"

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 24, 28, 24)
        }
        val scroll = ScrollView(this).apply { addView(root) }
        setContentView(scroll)

        root.addView(TextView(this).apply {
            text = "Rooster Autonomous Engineer"
            textSize = 24f
            typeface = Typeface.DEFAULT_BOLD
        })
        root.addView(TextView(this).apply {
            text = "Mobile companion • connect to your Rooster computer"
            textSize = 15f
        })

        server = EditText(this).apply {
            hint = "Rooster PC address (example: http://192.168.1.20:8765)"
            setSingleLine(true)
        }
        root.addView(server)

        token = EditText(this).apply {
            hint = "Rooster API token"
            setSingleLine(true)
        }
        root.addView(token)

        root.addView(Button(this).apply {
            text = "CONNECT / STATUS"
            setOnClickListener { request("GET", "/status") }
        })
        root.addView(Button(this).apply {
            text = "EMERGENCY STOP"
            setOnClickListener { request("POST", "/stop") }
        })
        root.addView(Button(this).apply {
            text = "RESET STOP"
            setOnClickListener { request("POST", "/reset") }
        })

        root.addView(TextView(this).apply {
            text = "\nSafety note: this companion exposes only connection/status and emergency-stop controls. Engineering actions remain on the Rooster computer and stay behind RoosterGuard."
            textSize = 14f
        })

        status = TextView(this).apply {
            text = "\nStatus: Not connected"
            textSize = 14f
        }
        root.addView(status)
    }

    private fun request(method: String, path: String) {
        val base = server.text.toString().trim().trimEnd('/')
        val apiToken = token.text.toString().trim()
        if (base.isEmpty() || apiToken.isEmpty()) {
            Toast.makeText(this, "Enter the Rooster PC address and API token.", Toast.LENGTH_SHORT).show()
            return
        }
        status.text = "Status: contacting Rooster..."
        executor.execute {
            try {
                val connection = (URL(base + path).openConnection() as HttpURLConnection).apply {
                    requestMethod = method
                    connectTimeout = 5000
                    readTimeout = 10000
                    setRequestProperty("Authorization", "Bearer $apiToken")
                    setRequestProperty("Accept", "application/json")
                }
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val body = stream?.bufferedReader()?.use { it.readText() } ?: ""
                runOnUiThread { status.text = "HTTP $code\n$body" }
                connection.disconnect()
            } catch (error: Exception) {
                runOnUiThread { status.text = "Connection failed\n${error.message}" }
            }
        }
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
