package com.rooster.autonomous

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.Executors

class MainActivity : Activity(), TextToSpeech.OnInitListener {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var server: EditText
    private lateinit var token: EditText
    private lateinit var objective: EditText
    private lateinit var chatInput: EditText
    private lateinit var status: TextView
    private lateinit var chatLog: TextView
    private var speechRecognizer: SpeechRecognizer? = null
    private var textToSpeech: TextToSpeech? = null
    private val conversation = JSONArray()
    @Volatile private var activeTaskId: String? = null
    private var voiceReplyEnabled = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Rooster AI"
        textToSpeech = TextToSpeech(this, this)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 24, 28, 24)
        }
        val scroll = ScrollView(this).apply { addView(root) }
        setContentView(scroll)

        root.addView(TextView(this).apply {
            text = "ROOSTER AI"
            textSize = 28f
            typeface = Typeface.DEFAULT_BOLD
        })
        root.addView(TextView(this).apply {
            text = "Your voice-enabled AI companion and Rooster PC control"
            textSize = 15f
        })

        server = EditText(this).apply {
            hint = "Rooster PC HTTPS address"
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
            text = "CONNECT / CHECK STATUS"
            setOnClickListener { request("GET", "/status") }
        })

        root.addView(TextView(this).apply {
            text = "\nTALK TO ROOSTER"
            textSize = 18f
            typeface = Typeface.DEFAULT_BOLD
        })
        chatLog = TextView(this).apply {
            text = "Rooster: Hey! Connect to your Rooster PC, then type or tap the microphone to talk."
            textSize = 16f
            setPadding(12, 12, 12, 12)
        }
        root.addView(chatLog)

        chatInput = EditText(this).apply {
            hint = "Say or type anything..."
            minLines = 2
            maxLines = 5
            gravity = Gravity.TOP
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        }
        root.addView(chatInput, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ))
        val chatButtons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        chatButtons.addView(Button(this).apply {
            text = "🎙 TALK"
            setOnClickListener { startListening() }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        chatButtons.addView(Button(this).apply {
            text = "SEND"
            setOnClickListener { sendChat() }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        chatButtons.addView(Button(this).apply {
            text = "🔊 VOICE ON"
            setOnClickListener {
                voiceReplyEnabled = !voiceReplyEnabled
                text = if (voiceReplyEnabled) "🔊 VOICE ON" else "🔇 VOICE OFF"
                Toast.makeText(this@MainActivity, if (voiceReplyEnabled) "Spoken replies enabled" else "Spoken replies muted", Toast.LENGTH_SHORT).show()
            }
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        root.addView(chatButtons)

        root.addView(TextView(this).apply {
            text = "\nROOSTER ENGINEERING CONTROLS"
            textSize = 18f
            typeface = Typeface.DEFAULT_BOLD
        })
        objective = EditText(this).apply {
            hint = "Tell Rooster what engineering task to perform on your PC"
            minLines = 3
            maxLines = 6
            gravity = Gravity.TOP
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
                    Toast.makeText(this@MainActivity, "Start a task first in this app session.", Toast.LENGTH_SHORT).show()
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

        status = TextView(this).apply {
            text = "\nStatus: Not connected"
            textSize = 14f
        }
        root.addView(status)
        root.addView(TextView(this).apply {
            text = "\nSafety: spoken conversation does not itself execute commands. Use Run Autonomous Task for engineering work. RoosterGuard, task limits, protected-path rules, audit logging, and emergency stop remain active. Use a trusted network and never expose this API directly to the public internet."
            textSize = 14f
        })
    }

    override fun onInit(result: Int) {
        if (result == TextToSpeech.SUCCESS) {
            textToSpeech?.language = Locale.US
        }
    }

    private fun startListening() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Toast.makeText(this, "Speech recognition is not available on this phone.", Toast.LENGTH_LONG).show()
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 41)
            return
        }
        try {
            speechRecognizer?.destroy()
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).also { recognizer ->
                recognizer.setRecognitionListener(object : RecognitionListener {
                    override fun onReadyForSpeech(params: Bundle?) {
                        runOnUiThread { status.text = "Status: Listening… speak now." }
                    }
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {
                        runOnUiThread { status.text = "Status: Processing your voice…" }
                    }
                    override fun onError(error: Int) {
                        runOnUiThread { status.text = "Voice input error ($error). Tap TALK and try again." }
                    }
                    override fun onResults(results: Bundle?) {
                        val spoken = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                        runOnUiThread {
                            if (!spoken.isNullOrBlank()) {
                                chatInput.setText(spoken)
                                chatInput.setSelection(chatInput.text.length)
                                sendChat()
                            } else {
                                status.text = "Status: I didn't catch that. Try again."
                            }
                        }
                    }
                    override fun onPartialResults(partialResults: Bundle?) {}
                    override fun onEvent(eventType: Int, params: Bundle?) {}
                })
                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.US.toLanguageTag())
                    putExtra(RecognizerIntent.EXTRA_PROMPT, "Talk to Rooster")
                }
                recognizer.startListening(intent)
            }
        } catch (error: Exception) {
            status.text = "Unable to start microphone: ${error.message}"
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 41 && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            startListening()
        } else if (requestCode == 41) {
            Toast.makeText(this, "Microphone permission is needed for voice input.", Toast.LENGTH_LONG).show()
        }
    }

    private fun sendChat() {
        val message = chatInput.text.toString().trim()
        if (message.isEmpty()) return
        if (server.text.toString().trim().isEmpty() || token.text.toString().trim().isEmpty()) {
            Toast.makeText(this, "Enter the Rooster PC address and API token first.", Toast.LENGTH_SHORT).show()
            return
        }
        conversation.put(JSONObject().put("role", "user").put("content", message))
        chatInput.setText("")
        renderConversation()
        status.text = "Status: Rooster is thinking…"
        val body = JSONObject().put("messages", conversation)
        executor.execute {
            var connection: HttpURLConnection? = null
            try {
                connection = openConnection("POST", "/chat", body.toString())
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val responseText = stream?.bufferedReader()?.use { it.readText() } ?: ""
                if (code !in 200..299) throw IllegalStateException("HTTP $code: $responseText")
                val reply = JSONObject(responseText).optString("reply").ifBlank { "I couldn't form a reply. Try again." }
                runOnUiThread {
                    conversation.put(JSONObject().put("role", "assistant").put("content", reply))
                    while (conversation.length() > 20) conversation.remove(0)
                    renderConversation()
                    status.text = "Status: Connected to Rooster"
                    if (voiceReplyEnabled) textToSpeech?.speak(reply, TextToSpeech.QUEUE_FLUSH, null, "rooster-reply")
                }
            } catch (error: Exception) {
                runOnUiThread { status.text = "Chat failed: ${error.message}" }
            } finally {
                connection?.disconnect()
            }
        }
    }

    private fun renderConversation() {
        val lines = mutableListOf<String>()
        for (i in 0 until conversation.length()) {
            val item = conversation.optJSONObject(i) ?: continue
            val role = if (item.optString("role") == "user") "YOU" else "ROOSTER"
            lines.add("$role: ${item.optString("content")}")
        }
        chatLog.text = lines.joinToString("\n\n").ifBlank { "Rooster: Ready when you are." }
    }

    private fun openConnection(method: String, path: String, body: String? = null): HttpURLConnection {
        val base = server.text.toString().trim().trimEnd('/')
        val apiToken = token.text.toString().trim()
        return (URL(base + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 7000
            readTimeout = 35000
            setRequestProperty("Authorization", "Bearer $apiToken")
            setRequestProperty("Accept", "application/json")
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }
        }
    }

    private fun request(method: String, path: String, body: String? = null) {
        val base = server.text.toString().trim().trimEnd('/')
        val apiToken = token.text.toString().trim()
        if (base.isEmpty() || apiToken.isEmpty()) {
            Toast.makeText(this, "Enter the Rooster PC address and API token.", Toast.LENGTH_SHORT).show()
            return
        }
        status.text = "Status: contacting Rooster…"
        executor.execute {
            var connection: HttpURLConnection? = null
            try {
                connection = openConnection(method, path, body)
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
        speechRecognizer?.destroy()
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        executor.shutdownNow()
        super.onDestroy()
    }
}
