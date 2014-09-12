
#include <iostream>
#include <array>

using std::cout;
using std::endl;

int main() {
    cout << "CRABSYS RULEZ!!!11" << endl;

    std::array<int, 3> a = {1,2,3};

    for ( auto x : a ) {
        cout << x << endl;
    }

    return 0;
}

