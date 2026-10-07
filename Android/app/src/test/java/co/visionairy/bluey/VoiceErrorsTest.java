package co.visionairy.bluey;
import org.junit.Test;
import static org.junit.Assert.*;

public class VoiceErrorsTest {
    @Test public void harmlessRacesDoNotEndSession() {
        assertTrue(VoiceErrors.recoverable("response_cancel_not_active"));
        assertTrue(VoiceErrors.recoverable("conversation_already_has_active_response"));
        assertFalse(VoiceErrors.recoverable("invalid_api_key"));
    }
    @Test public void errorsDoNotExposeUntrustedMessages() {
        assertEquals("unknown", VoiceErrors.safeCode("secret value with spaces"));
        assertEquals("unknown", VoiceErrors.safeCode(null));
        assertTrue(VoiceErrors.message("insufficient_quota").contains("usage limit"));
        assertFalse(VoiceErrors.recoverable("credit_balance_exhausted"));
        assertTrue(VoiceErrors.message("credit_balance_exhausted").contains("API credit is exhausted"));
    }
}
