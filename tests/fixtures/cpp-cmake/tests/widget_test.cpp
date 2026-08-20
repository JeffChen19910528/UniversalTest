#include <gtest/gtest.h>

#include "../src/widget.hpp"

TEST(WidgetTest, Add) {
    EXPECT_EQ(add(2, 3), 5);
}
