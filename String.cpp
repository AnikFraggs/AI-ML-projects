//Even sem all java codes:
#include <vector>
#include <string>
#include <utility>

using namespace std;

vector<pair<char, int>> compress(const string& s) {
    vector<pair<char, int>> result;
    if (s.empty()) return result;

    char current = s[0];
    int count = 1;

    for (int i = 1; i < s.size(); i++) {
        if (s[i] == current) {
            count++;
        } else {
            result.push_back({current, count});
            current = s[i];
            count = 1;
        }
    }

    // push last group
    result.push_back({current, count});

    return result;
}
