
#include <mysql.h>

#include <iostream>

using namespace std;

int main() {
    cout << "MySQL dependency test" << endl;

    MYSQL *mysql = mysql_init(NULL);

    return 0;
}
