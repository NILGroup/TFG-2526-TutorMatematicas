using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace MathTutor.PageModels
{
    /// <summary>
    /// Page model for SettingsPage.
    ///
    /// Settings are stored in <see cref="Preferences.Default"/> (per-device,
    /// platform-managed). Values are read on construction and written on Save.
    ///
    /// Note: study-related preferences (KC interests, difficulty target,
    /// objective, course) live on the user document and are edited via
    /// the Profile / Questionnaire flow. This page is for app-level
    /// settings: appearance, notifications, hint behaviour.
    /// </summary>
    public partial class SettingsPageModel : ObservableObject
    {
        // ── Preferences keys (private constants — single source of truth) ──
        private const string KeyTheme = "settings.theme";
        private const string KeyHintBehavior = "settings.hint_behavior";
        private const string KeyNotifyDaily = "settings.notify_daily";
        private const string KeyNotifyTime = "settings.notify_time";
        private const string KeySoundOn = "settings.sound_on";

        // ── Observable properties ──────────────────────────────────────────

        /// <summary>"Sistema" / "Claro" / "Oscuro".</summary>
        [ObservableProperty] private string selectedTheme = "Sistema";

        /// <summary>"Sin pistas" / "Pistas primero" / "Respuesta completa".</summary>
        [ObservableProperty] private string hintBehavior = "Pistas primero";

        [ObservableProperty] private bool notifyDailyReminder = true;

        /// <summary>Time of day for the daily reminder (default 18:00).</summary>
        [ObservableProperty] private TimeSpan notifyTime = new(18, 0, 0);

        [ObservableProperty] private bool soundOn = true;

        [ObservableProperty] private string? statusMessage;

        // ── Picker option lists ────────────────────────────────────────────
        public List<string> ThemeOptions { get; } =
            new() { "Sistema", "Claro", "Oscuro" };

        public List<string> HintBehaviorOptions { get; } =
            new() { "Sin pistas", "Pistas primero", "Respuesta completa" };

        public SettingsPageModel()
        {
            LoadFromPreferences();
        }

        // ── Persistence ────────────────────────────────────────────────────

        private void LoadFromPreferences()
        {
            SelectedTheme = Preferences.Default.Get(KeyTheme, "Sistema");
            HintBehavior = Preferences.Default.Get(KeyHintBehavior, "Pistas primero");
            NotifyDailyReminder = Preferences.Default.Get(KeyNotifyDaily, true);
            SoundOn = Preferences.Default.Get(KeySoundOn, true);

            // TimeSpan isn't natively supported by Preferences — store as ticks
            var ticks = Preferences.Default.Get(KeyNotifyTime, new TimeSpan(18, 0, 0).Ticks);
            NotifyTime = new TimeSpan(ticks);
        }

        [RelayCommand]
        private async Task SaveSettings()
        {
            Preferences.Default.Set(KeyTheme, SelectedTheme);
            Preferences.Default.Set(KeyHintBehavior, HintBehavior);
            Preferences.Default.Set(KeyNotifyDaily, NotifyDailyReminder);
            Preferences.Default.Set(KeyNotifyTime, NotifyTime.Ticks);
            Preferences.Default.Set(KeySoundOn, SoundOn);

            // Apply the theme immediately
            ApplyTheme(SelectedTheme);

            StatusMessage = "Ajustes guardados ✓";

            // Clear status after a short while so the banner doesn't stick around
            await Task.Delay(2500);
            StatusMessage = null;
        }

        [RelayCommand]
        private void ResetDefaults()
        {
            SelectedTheme = "Sistema";
            HintBehavior = "Pistas primero";
            NotifyDailyReminder = true;
            NotifyTime = new TimeSpan(18, 0, 0);
            SoundOn = true;
        }

        // ── Theme switching ────────────────────────────────────────────────

        /// <summary>
        /// Apply the chosen theme by updating <c>UserAppTheme</c>.
        /// Called both on Save and whenever the user changes the picker.
        /// </summary>
        private static void ApplyTheme(string theme)
        {
            if (Application.Current is null) return;

            Application.Current.UserAppTheme = theme switch
            {
                "Claro" => AppTheme.Light,
                "Oscuro" => AppTheme.Dark,
                _ => AppTheme.Unspecified,   // follow system
            };
        }

        // Apply the theme live as the user picks it (without waiting for Save)
        partial void OnSelectedThemeChanged(string oldValue, string newValue) => ApplyTheme(newValue);
    }
}
