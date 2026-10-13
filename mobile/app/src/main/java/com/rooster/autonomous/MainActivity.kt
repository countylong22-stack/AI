package com.rooster.autonomous

import android.app.Activity
import android.graphics.Typeface
import android.os.Bundle
import android.text.InputType
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var server: EditText
    private lateinit var token: EditText
    private lateinit var objective: EditText
    private lateinit var status: TextView
    @Volatile private var activeTaskId: String? = null

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
            text = "Mobile control • submit a bounded autonomous engineering task to your Rooster PC"
            textSize = 15f
        })

        server = EditText(this).apply {
            hint = "Rooster PC address (example: http://192.168.1.20:8765)"
            setSingleLine(true)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        }
        root.addView(server)

        token = EditText(this).apply {
            hint = "Rooster API token"
            setSingleLine(true)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        root.addView(token)

        root.addView(Button(this).apply {
            text = "CONNECT / STATUS"
            setOnClickListener { request("GET", "/status") }
        })

        objective = EditText(this).apply {
            hint = "What should Rooster work on? Be specific about the result you want."
            minLines = 3
            maxLines = 6
            gravity = android.view.Gravity.TOP
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        }
        root.addView(objective, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ))

        root.addView(Button(this).apply {
            text = "RUN AUTONOMOUS TASK"
            setOnClickListener {
                val task = objective.text.toString().trim()
                if (task.isEmpty()) {
                    Toast.makeText(this@MainActivity, "Enter a task for Rooster first.", Toast.LENGTH_SHORT).show()
                } else {
                    request("POST", "/tasks", JSONObject().put("objective", task).toString())
                }
            }
        })
        root.addView(Button(this).apply {
            text = "REFRESH TASK STATUS"
            setOnClickListener {
                val id = activeTaskId
                if (id.isNullOrBlank()) {
                    Toast.makeText(this@MainActivity, "Start a task first on this app session.", Toast.LENGTH_SHORT).show()
                } else {
                    request("GET", "/tasks/$id")
                }
            }
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
            text = "\nSafety: Rooster runs on your PC, not on the phone. Autonomous changes remain bounded by RoosterGuard, iteration limits, protected-path rules, test verification, and the emergency stop. Use only on a trusted home network; never port-forward this API to the internet."
            textSize = 14f
        })

        status = TextView(this).apply {
            text = "\nStatus: Not connected"
            textSize = 14f
        }
        root.addView(status)
    }

    private fun request(method: String, path: String, body: String? = null) {
        val base = server.text.toString().trim().trimEnd('/')
        val apiToken = token.text.toString().trim()
        if (base.isEmpty() || apiToken.isEmpty()) {
            Toast.makeText(this, "Enter the Rooster PC address and API token.", Toast.LENGTH_SHORT).show()
            return
        }
        status.text = "Status: contacting Rooster..."
        executor.execute {
            var connection: HttpURLConnection? = null
            try {
                connection = (URL(base + path).openConnection() as HttpURLConnection).apply {
                    requestMethod = method
                    connectTimeout = 5000
                    readTimeout = 15000
                    setRequestProperty("Authorization", "Bearer $apiToken")
                    setRequestProperty("Accept", "application/json")
                    if (body != null) {
                        doOutput = true
                        setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    }
                }
                if (body != null) {
                    connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                }
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val response = stream?.bufferedReader()?.use { it.readText() } ?: ""
                if (code in 200..299 && path == "/tasks") {
                    val taskId = JSONObject(response).optString("task_id")
                    if (taskId.isNotBlank()) activeTaskId = taskId
                }
                runOnUiThread {
                    status.text = "HTTP $code\n$response" +
                        (activeTaskId?.let { "\nActive task ID: $it" } ?: "")
                }
            } catch (error: Exception) {
                runOnUiThread { status.text = "Connection failed\n${error.message}" }
            } finally {
                connection?.disconnect()
            }
        }
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }
}
