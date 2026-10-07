package co.visionairy.bluey;

final class VoiceErrors {
    static String safeCode(String value) {
        return value != null && value.matches("[a-zA-Z0-9_]{1,100}") ? value : "unknown";
    }
    static boolean recoverable(String code) {
        return code.equals("input_audio_buffer_commit_empty") || code.equals("response_cancel_not_active")
            || code.equals("conversation_already_has_active_response");
    }
    static String message(String code) {
        if (code.equals("credit_balance_exhausted"))
            return "OpenAI API credit is exhausted. Add credit to the API project, then wake Bluey again. Phone pairing is still connected.";
        if (code.equals("insufficient_quota") || code.equals("rate_limit_exceeded"))
            return "Voice account usage limit reached. Check OpenAI API billing or try again shortly.";
        if (code.equals("invalid_api_key") || code.equals("authentication_error"))
            return "Voice authorization expired or was rejected. Double tap to reconnect.";
        return "Voice service error (" + safeCode(code) + "). Double tap to reconnect.";
    }
}
