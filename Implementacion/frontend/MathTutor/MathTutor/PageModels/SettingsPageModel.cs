using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using System.Threading.Tasks;

namespace MathTutor.PageModels
{
    public partial class SettingsPageModel : ObservableObject
    {
        [ObservableProperty] private int dailyProblemsCount = 10;
        [ObservableProperty] private int difficultyMin = 1;
        [ObservableProperty] private int difficultyMax = 3;
        [ObservableProperty] private string hintsPreference = "Pistas primero";

        public List<string> HintOptions { get; } =
            new() { "Sin pistas", "Pistas primero", "Respuesta completa" };

        public SettingsPageModel() { }

        [RelayCommand]
        private async Task SaveSettings()
        {
            // Persist settings locally or via backend

            var app = Application.Current;
            var page = (app != null && app.Windows != null && app.Windows.Count > 0)
                ? app.Windows[0].Page
                : null;

            if (page != null)
            {
                // Use the async API and await it (avoids obsolete API and null dereference)
                await page.DisplayAlertAsync("Ajustes", "Ajustes guardados.", "OK");
            }
            else
            {
                // No available page to show an alert on; nothing to do.
                await Task.CompletedTask;
            }
        }
    }
}
