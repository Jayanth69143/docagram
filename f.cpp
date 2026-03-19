#include <iostream>
#include <cmath>

using namespace std;

struct vec3 {
    float x, y, z;
    vec3(float x=0, float y=0, float z=0) : x(x), y(y), z(z) {}
    vec3 operator+(const vec3& other) const {
        return vec3(x + other.x, y + other.y, z + other.z);
    }
};

float length(const vec3& v) {
    return sqrt(v.x*v.x + v.y*v.y + v.z*v.z);
}

float kernal(vec3 ver) {
    vec3 a;
    float b, c, d, e;
    a = ver;
    for (int i = 0; i < 5; i++) {
        b = length(a);
        c = atan2(a.y, a.x) * 8.0;
        e = 1.0 / b;
        d = acos(a.z / b) * 8.0;
        b = pow(b, 8.0);
        a = vec3(b * sin(d) * cos(c), b * sin(d) * sin(c), b * cos(d)) + ver;
        if (b > 6.0) {
            break;
        }
    }
    return 4.0 - a.x * a.x - a.y * a.y - a.z * a.z;
}

int main() {
    // Example usage
    vec3 v(1.0, 2.0, 3.0);
    float result = kernal(v);
    cout << "Result: " << result << endl;
    return 0;
}
