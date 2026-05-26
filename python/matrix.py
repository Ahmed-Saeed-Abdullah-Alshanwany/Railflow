class Solution:
    def flipAndInvertImage(self, image: list[list[int]]) -> list[list[int]]:
        for row in image :
            row.reverse()
            row[:] = [1 ^ element for element in row]
        return image
    
image = [
    [0, 1, 0],
    [1, 0, 0],
    [0, 0, 1]
]

# Create an instance of the Solution class
solution = Solution()

# Call the flipAndInvertImage method
flipped_inverted_image = solution.flipAndInvertImage(image)

# Print the result
print(flipped_inverted_image)