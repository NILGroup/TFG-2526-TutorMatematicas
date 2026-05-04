using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace MathTutor
{
    public class ApiService
    {
        private readonly HttpClient _client;

        private readonly JsonSerializerOptions _jsonOptions = new()
        {
            PropertyNameCaseInsensitive = true
        };

        public ApiService(string baseUrl)
        {
            _client = new HttpClient
            {
                BaseAddress = new Uri(baseUrl)
            };
        }

        // --------------------------------------------------
        // GET
        // --------------------------------------------------
        public async Task<T?> GetAsync<T>(string path)
        {
            try
            {
                using HttpResponseMessage resp = await _client.GetAsync(path);

                string json = await resp.Content.ReadAsStringAsync();

                System.Diagnostics.Debug.WriteLine($"GET {path} -> {(int)resp.StatusCode}");
                System.Diagnostics.Debug.WriteLine(json);

                resp.EnsureSuccessStatusCode();

                if (string.IsNullOrWhiteSpace(json))
                    return default;

                return JsonSerializer.Deserialize<T>(json, _jsonOptions);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"GET ERROR {path}: {ex}");
                return default;
            }
        }

        // --------------------------------------------------
        // POST
        // --------------------------------------------------
        public async Task<T?> PostAsync<T>(string path, object payload)
        {
            try
            {
                string jsonPayload = JsonSerializer.Serialize(payload);

                using HttpResponseMessage resp = await _client.PostAsync(
                    path,
                    new StringContent(jsonPayload, Encoding.UTF8, "application/json")
                );

                string json = await resp.Content.ReadAsStringAsync();

                System.Diagnostics.Debug.WriteLine($"POST {path} -> {(int)resp.StatusCode}");
                System.Diagnostics.Debug.WriteLine(json);

                resp.EnsureSuccessStatusCode();

                if (string.IsNullOrWhiteSpace(json))
                    return default;

                return JsonSerializer.Deserialize<T>(json, _jsonOptions);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"POST ERROR {path}: {ex}");
                return default;
            }
        }

        // --------------------------------------------------
        // PUT
        // --------------------------------------------------
        public async Task<T?> PutAsync<T>(string path, object payload)
        {
            try
            {
                string jsonPayload = JsonSerializer.Serialize(payload);

                using HttpResponseMessage resp = await _client.PutAsync(
                    path,
                    new StringContent(jsonPayload, Encoding.UTF8, "application/json")
                );

                string json = await resp.Content.ReadAsStringAsync();

                System.Diagnostics.Debug.WriteLine($"PUT {path} -> {(int)resp.StatusCode}");
                System.Diagnostics.Debug.WriteLine(json);

                resp.EnsureSuccessStatusCode();

                if (string.IsNullOrWhiteSpace(json))
                    return default;

                return JsonSerializer.Deserialize<T>(json, _jsonOptions);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"PUT ERROR {path}: {ex}");
                return default;
            }
        }
    }
}