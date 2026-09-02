package com.sindromegames.chatoverlay;

import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.sindromegames.chatoverlay.providers.YouTubeMode;
import com.sindromegames.chatoverlay.settings.AppSettings;
import com.sindromegames.chatoverlay.settings.SecureStore;
import com.sindromegames.chatoverlay.settings.YouTubeKeyValidator;
import com.sindromegames.chatoverlay.sound.NotificationSoundPlayer;
import com.sindromegames.chatoverlay.util.UrlNormalizer;

import java.util.ArrayList;
import java.util.List;

public final class SettingsActivity extends AppCompatActivity {
    private enum KeyState { UNCHANGED, CHECKING, VALID, INVALID, UNAVAILABLE }

    private AppSettings settings;
    private SecureStore secureStore;
    private String originalKey;
    private KeyState keyState = KeyState.UNCHANGED;
    private final YouTubeKeyValidator validator = new YouTubeKeyValidator();
    private final NotificationSoundPlayer soundPlayer = new NotificationSoundPlayer();
    private final Handler debounce = new Handler(Looper.getMainLooper());
    private Runnable pendingValidation;

    private Spinner language;
    private CheckBox twitchEnabled, youtubeEnabled, autoScroll, showTimestamps, showPlatform,
            hideCommands, soundEnabled;
    private EditText twitchChannel, youtubeInput, apiKey;
    private TextView modeTitle, modeDetail, opacityLabel, fontLabel, maximumLabel,
            volumeLabel, intervalLabel;
    private LinearLayout advanced;
    private Button advancedButton, revealButton;
    private SeekBar opacity, fontSize, maximum, volume, interval;
    private Spinner twitchSound, youtubeSound;

    @Override protected void onCreate(Bundle savedInstanceState) {
        AppSettings.applyLocale(this);
        super.onCreate(savedInstanceState);
        settings = AppSettings.load(this);
        secureStore = new SecureStore(this);
        originalKey = secureStore.readApiKey();
        buildUi();
        bindValues();
        renderMode();
    }

    @Override protected void onDestroy() {
        if (pendingValidation != null) debounce.removeCallbacks(pendingValidation);
        validator.close();
        soundPlayer.stop();
        super.onDestroy();
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(12), dp(16), dp(28));
        root.setBackgroundColor(ContextCompat.getColor(this, R.color.surface));
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout top = row();
        TextView title = sectionTitle(R.string.settings_title);
        top.addView(title, new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        Button cancel = new Button(this); cancel.setText(R.string.cancel); cancel.setOnClickListener(v -> finish());
        top.addView(cancel);
        root.addView(top);

        root.addView(label(R.string.language));
        language = spinner(new String[]{getString(R.string.language_english),
                getString(R.string.language_portuguese)});
        root.addView(language);

        root.addView(sectionTitle(R.string.channels));
        twitchEnabled = check(R.string.enable_twitch); root.addView(twitchEnabled);
        root.addView(label(R.string.twitch_channel));
        twitchChannel = field(R.string.twitch_channel_hint, false); root.addView(twitchChannel);
        youtubeEnabled = check(R.string.enable_youtube); root.addView(youtubeEnabled);
        root.addView(label(R.string.youtube_channel));
        youtubeInput = field(R.string.youtube_channel_hint, false); root.addView(youtubeInput);

        root.addView(label(R.string.connection_mode));
        LinearLayout statusPanel = new LinearLayout(this);
        statusPanel.setOrientation(LinearLayout.VERTICAL);
        statusPanel.setPadding(dp(10), dp(8), dp(10), dp(8));
        statusPanel.setBackgroundResource(R.drawable.bg_status);
        modeTitle = new TextView(this); modeTitle.setTextColor(Color.WHITE); modeTitle.setTextSize(14);
        modeTitle.setTypeface(null, android.graphics.Typeface.BOLD);
        modeDetail = new TextView(this); modeDetail.setTextColor(
                ContextCompat.getColor(this, R.color.text_secondary)); modeDetail.setTextSize(12);
        statusPanel.addView(modeTitle); statusPanel.addView(modeDetail);
        root.addView(statusPanel, margins(0, 4, 0, 8));

        advancedButton = new Button(this);
        advancedButton.setText(getString(R.string.advanced_settings) + "  ▾");
        advancedButton.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        root.addView(advancedButton);
        advanced = new LinearLayout(this); advanced.setOrientation(LinearLayout.VERTICAL);
        advanced.setVisibility(View.GONE);
        advanced.setPadding(dp(8), 0, dp(8), dp(8));
        advancedButton.setOnClickListener(view -> {
            boolean opening = advanced.getVisibility() != View.VISIBLE;
            advanced.setVisibility(opening ? View.VISIBLE : View.GONE);
            advancedButton.setText(getString(R.string.advanced_settings) + (opening ? "  ▴" : "  ▾"));
            if (!opening) hideKey();
        });
        advanced.addView(label(R.string.youtube_api_key));
        LinearLayout keyRow = row();
        apiKey = field(0, true);
        keyRow.addView(apiKey, new LinearLayout.LayoutParams(0, dp(52), 1));
        revealButton = new Button(this); revealButton.setText(R.string.show_key);
        revealButton.setOnClickListener(view -> toggleKeyVisibility());
        keyRow.addView(revealButton, new LinearLayout.LayoutParams(dp(88), dp(52)));
        advanced.addView(keyRow);
        advanced.addView(helper(R.string.youtube_api_key_description));
        TextView clarification = helper(R.string.youtube_api_key_not_stream_key);
        clarification.setTextColor(ContextCompat.getColor(this, R.color.warning));
        advanced.addView(clarification);
        Button validate = new Button(this); validate.setText(R.string.validate_key);
        validate.setOnClickListener(view -> validateKey()); advanced.addView(validate);
        root.addView(advanced);

        root.addView(sectionTitle(R.string.appearance));
        opacityLabel = label(0); root.addView(opacityLabel);
        opacity = seek(100); root.addView(opacity);
        fontLabel = label(0); root.addView(fontLabel);
        fontSize = seek(19); root.addView(fontSize);
        maximumLabel = label(0); root.addView(maximumLabel);
        maximum = seek(48); root.addView(maximum);
        autoScroll = check(R.string.auto_scroll); root.addView(autoScroll);
        showTimestamps = check(R.string.show_timestamps); root.addView(showTimestamps);
        showPlatform = check(R.string.show_platform); root.addView(showPlatform);
        hideCommands = check(R.string.hide_commands); root.addView(hideCommands);

        root.addView(sectionTitle(R.string.sound));
        soundEnabled = check(R.string.enable_sound); root.addView(soundEnabled);
        volumeLabel = label(0); root.addView(volumeLabel);
        volume = seek(200); root.addView(volume);
        root.addView(label(R.string.twitch_sound));
        LinearLayout twitchSoundRow = row();
        twitchSound = soundSpinner(); twitchSoundRow.addView(twitchSound,
                new LinearLayout.LayoutParams(0, dp(52), 1));
        Button testTwitch = new Button(this); testTwitch.setText(R.string.test_sound);
        testTwitch.setOnClickListener(view -> preview(twitchSound)); twitchSoundRow.addView(testTwitch);
        root.addView(twitchSoundRow);
        root.addView(label(R.string.youtube_sound));
        LinearLayout youtubeSoundRow = row();
        youtubeSound = soundSpinner(); youtubeSoundRow.addView(youtubeSound,
                new LinearLayout.LayoutParams(0, dp(52), 1));
        Button testYouTube = new Button(this); testYouTube.setText(R.string.test_sound);
        testYouTube.setOnClickListener(view -> preview(youtubeSound)); youtubeSoundRow.addView(testYouTube);
        root.addView(youtubeSoundRow);
        intervalLabel = label(0); root.addView(intervalLabel);
        interval = seek(50); root.addView(interval);

        Button save = new Button(this); save.setText(R.string.save);
        save.setOnClickListener(view -> saveOrValidate());
        LinearLayout.LayoutParams saveParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(56)); saveParams.topMargin = dp(18);
        root.addView(save, saveParams);
        setContentView(scroll);
        attachListeners();
    }

    private void bindValues() {
        language.setSelection(settings.language.startsWith("pt") ? 1 : 0);
        twitchEnabled.setChecked(settings.twitchEnabled); twitchChannel.setText(settings.twitchChannel);
        youtubeEnabled.setChecked(settings.youtubeEnabled); youtubeInput.setText(settings.youtubeInput);
        apiKey.setText(originalKey);
        opacity.setProgress(settings.backgroundOpacity);
        fontSize.setProgress(settings.fontSize - 11);
        maximum.setProgress((settings.maxMessages - 20) / 10);
        autoScroll.setChecked(settings.autoScroll); showTimestamps.setChecked(settings.showTimestamps);
        showPlatform.setChecked(settings.showPlatform); hideCommands.setChecked(settings.hideCommands);
        soundEnabled.setChecked(settings.soundEnabled); volume.setProgress(settings.soundVolume);
        twitchSound.setSelection(soundPosition(settings.twitchSound));
        youtubeSound.setSelection(soundPosition(settings.youtubeSound));
        interval.setProgress(settings.soundMinIntervalMs / 100);
        updateSeekLabels();
        apiKey.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                String current = s.toString().trim();
                keyState = current.equals(originalKey) ? KeyState.UNCHANGED
                        : current.isEmpty() ? KeyState.VALID : KeyState.UNAVAILABLE;
                renderMode(); scheduleValidation(current);
            }
            @Override public void afterTextChanged(Editable s) {}
        });
    }

    private void attachListeners() {
        SeekBar.OnSeekBarChangeListener listener = new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                updateSeekLabels();
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        };
        opacity.setOnSeekBarChangeListener(listener); fontSize.setOnSeekBarChangeListener(listener);
        maximum.setOnSeekBarChangeListener(listener); volume.setOnSeekBarChangeListener(listener);
        interval.setOnSeekBarChangeListener(listener);
    }

    private void scheduleValidation(String key) {
        if (pendingValidation != null) debounce.removeCallbacks(pendingValidation);
        if (key.isEmpty() || key.equals(originalKey)) return;
        pendingValidation = () -> validateKeyValue(key, false);
        debounce.postDelayed(pendingValidation, 750);
    }

    private void validateKey() { validateKeyValue(apiKey.getText().toString().trim(), false); }

    private void validateKeyValue(String key, boolean saveAfter) {
        if (key.isEmpty()) {
            keyState = KeyState.VALID; renderMode();
            if (saveAfter) doSave();
            return;
        }
        keyState = KeyState.CHECKING; renderMode();
        validator.validate(key, result -> {
            if (!apiKey.getText().toString().trim().equals(key)) return;
            keyState = switch (result) {
                case VALID -> KeyState.VALID;
                case INVALID -> KeyState.INVALID;
                case UNAVAILABLE -> KeyState.UNAVAILABLE;
            };
            renderMode();
            if (saveAfter && keyState != KeyState.INVALID) doSave();
        });
    }

    private void saveOrValidate() {
        String current = apiKey.getText().toString().trim();
        if (keyState == KeyState.INVALID) {
            Toast.makeText(this, R.string.invalid_api_key_save, Toast.LENGTH_LONG).show(); return;
        }
        if (!current.isEmpty() && !current.equals(originalKey) && keyState != KeyState.VALID
                && keyState != KeyState.UNAVAILABLE) {
            validateKeyValue(current, true); return;
        }
        doSave();
    }

    private void doSave() {
        String twitch = UrlNormalizer.twitchChannel(twitchChannel.getText().toString());
        String youtube = UrlNormalizer.youtubeInput(youtubeInput.getText().toString());
        if ((twitchEnabled.isChecked() && twitch.isEmpty())
                || (youtubeEnabled.isChecked() && youtube.isEmpty())
                || (!twitchEnabled.isChecked() && !youtubeEnabled.isChecked())) {
            Toast.makeText(this, R.string.invalid_channel, Toast.LENGTH_LONG).show(); return;
        }
        settings.language = language.getSelectedItemPosition() == 1 ? "pt-BR" : "en";
        settings.twitchEnabled = twitchEnabled.isChecked(); settings.twitchChannel = twitch;
        settings.youtubeEnabled = youtubeEnabled.isChecked(); settings.youtubeInput = youtube;
        settings.backgroundOpacity = opacity.getProgress(); settings.fontSize = fontSize.getProgress() + 11;
        settings.maxMessages = maximum.getProgress() * 10 + 20;
        settings.autoScroll = autoScroll.isChecked(); settings.showTimestamps = showTimestamps.isChecked();
        settings.showPlatform = showPlatform.isChecked(); settings.hideCommands = hideCommands.isChecked();
        settings.soundEnabled = soundEnabled.isChecked(); settings.soundVolume = volume.getProgress();
        settings.twitchSound = soundId(twitchSound.getSelectedItemPosition());
        settings.youtubeSound = soundId(youtubeSound.getSelectedItemPosition());
        settings.soundMinIntervalMs = interval.getProgress() * 100;
        try {
            secureStore.writeApiKey(apiKey.getText().toString());
        } catch (Exception ignored) {
            Toast.makeText(this, R.string.settings_save_failed, Toast.LENGTH_LONG).show(); return;
        }
        settings.save(this);
        Toast.makeText(this, R.string.settings_saved, Toast.LENGTH_SHORT).show();
        setResult(RESULT_OK);
        AppSettings.applyLocale(this);
        finish();
    }

    private void renderMode() {
        String key = apiKey == null ? originalKey : apiKey.getText().toString().trim();
        ChatBus.State active = ChatBus.state();
        YouTubeMode mode = active.youtubeMode();
        int title, detail;
        if (keyState == KeyState.CHECKING) {
            title = detail = R.string.youtube_key_checking;
        } else if (keyState == KeyState.INVALID || mode == YouTubeMode.INVALID_KEY) {
            title = R.string.youtube_key_invalid; detail = R.string.youtube_key_invalid_detail;
        } else if (keyState == KeyState.UNAVAILABLE && !key.equals(originalKey)) {
            title = R.string.youtube_key_unverified; detail = R.string.youtube_key_unverified_detail;
        } else if (mode == YouTubeMode.OFFICIAL_STREAM) {
            title = R.string.youtube_mode_official; detail = R.string.youtube_mode_official_detail;
        } else if (mode == YouTubeMode.OFFICIAL_POLLING) {
            title = R.string.youtube_mode_official_polling; detail = R.string.youtube_mode_official_polling_detail;
        } else if (mode == YouTubeMode.COMPATIBILITY_FALLBACK) {
            title = R.string.youtube_mode_fallback; detail = R.string.youtube_mode_fallback_detail;
        } else if (key.isEmpty()) {
            title = R.string.youtube_mode_compatibility; detail = R.string.youtube_mode_compatibility_detail;
        } else {
            title = R.string.youtube_key_configured; detail = R.string.youtube_key_configured_detail;
        }
        modeTitle.setText(title); modeDetail.setText(detail);
    }

    private void toggleKeyVisibility() {
        boolean hidden = (apiKey.getInputType() & InputType.TYPE_TEXT_VARIATION_PASSWORD) != 0;
        apiKey.setInputType(InputType.TYPE_CLASS_TEXT | (hidden
                ? InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD : InputType.TYPE_TEXT_VARIATION_PASSWORD));
        revealButton.setText(hidden ? R.string.hide_key : R.string.show_key);
        apiKey.setSelection(apiKey.length());
    }

    private void hideKey() {
        apiKey.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        revealButton.setText(R.string.show_key);
    }

    private void preview(Spinner spinner) {
        soundPlayer.play(soundId(spinner.getSelectedItemPosition()), volume.getProgress(), 0, true);
    }

    private void updateSeekLabels() {
        opacityLabel.setText(getString(R.string.background_opacity, opacity.getProgress()));
        fontLabel.setText(getString(R.string.font_size, fontSize.getProgress() + 11));
        maximumLabel.setText(getString(R.string.max_messages, maximum.getProgress() * 10 + 20));
        volumeLabel.setText(getString(R.string.volume, volume.getProgress()));
        intervalLabel.setText(getString(R.string.antispam, interval.getProgress() * 100));
    }

    private Spinner soundSpinner() {
        return spinner(new String[]{getString(R.string.sound_soft), getString(R.string.sound_pop),
                getString(R.string.sound_chime), getString(R.string.sound_arcade),
                getString(R.string.sound_bubble), getString(R.string.sound_bell)});
    }

    private static String soundId(int position) {
        String[] ids = {"soft", "pop", "chime", "arcade", "bubble", "bell"};
        return ids[Math.max(0, Math.min(ids.length - 1, position))];
    }

    private static int soundPosition(String id) {
        String[] ids = {"soft", "pop", "chime", "arcade", "bubble", "bell"};
        for (int index = 0; index < ids.length; index++) if (ids[index].equals(id)) return index;
        return 0;
    }

    private LinearLayout row() {
        LinearLayout value = new LinearLayout(this); value.setOrientation(LinearLayout.HORIZONTAL);
        value.setGravity(Gravity.CENTER_VERTICAL); return value;
    }

    private TextView sectionTitle(int resource) {
        TextView view = label(resource); view.setTextSize(18); view.setTextColor(Color.WHITE);
        view.setTypeface(null, android.graphics.Typeface.BOLD);
        view.setPadding(0, dp(16), 0, dp(8)); return view;
    }

    private TextView label(int resource) {
        TextView view = new TextView(this); if (resource != 0) view.setText(resource);
        view.setTextColor(ContextCompat.getColor(this, R.color.text_primary)); view.setTextSize(13);
        view.setPadding(0, dp(7), 0, dp(3)); return view;
    }

    private TextView helper(int resource) {
        TextView view = label(resource); view.setTextColor(ContextCompat.getColor(this, R.color.text_secondary));
        view.setTextSize(12); return view;
    }

    private CheckBox check(int resource) {
        CheckBox value = new CheckBox(this); value.setText(resource); value.setTextColor(Color.WHITE);
        value.setMinHeight(dp(44)); return value;
    }

    private EditText field(int hint, boolean password) {
        EditText value = new EditText(this); if (hint != 0) value.setHint(hint);
        value.setTextColor(Color.WHITE); value.setHintTextColor(ContextCompat.getColor(this, R.color.text_secondary));
        value.setSingleLine(true); value.setInputType(InputType.TYPE_CLASS_TEXT
                | (password ? InputType.TYPE_TEXT_VARIATION_PASSWORD : InputType.TYPE_TEXT_VARIATION_URI));
        return value;
    }

    private SeekBar seek(int maximum) { SeekBar value = new SeekBar(this); value.setMax(maximum); return value; }

    private Spinner spinner(String[] values) {
        Spinner spinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, values);
        spinner.setAdapter(adapter); return spinner;
    }

    private LinearLayout.LayoutParams margins(int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(dp(left), dp(top), dp(right), dp(bottom)); return params;
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}

